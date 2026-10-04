"""Capa de datos SQLite.

Reemplaza los archivos DBF/CDX del original:

    EMPRESA.DBF                -> empresa
    <EMPRESA>\\RESPAL.DBF       -> periodo   (años de trabajo)
    <EMPRESA>\\CUENTAS.DBF      -> cuenta
    <EMPRESA>\\CCOSTO.DBF       -> ccosto
    <EMPRESA>\\TRAaaaa\\PROVEE   -> proveedor (por empresa, compartido entre años)
    <EMPRESA>\\TRAaaaa\\ASIENTOS -> asiento
    <EMPRESA>\\TRAaaaa\\DETASIEN -> detalle
    <EMPRESA>\\TRAaaaa\\COMPRAS  -> compra    (ligada a la línea de detalle)
    USUARIO.DBF                -> usuario

Todo queda en un único archivo .db; los montos se guardan como enteros (pesos).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import os
import secrets
import shutil
import sqlite3
from contextlib import contextmanager

from . import util

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS empresa (
    id           INTEGER PRIMARY KEY,
    rut          TEXT NOT NULL UNIQUE,
    razon_social TEXT NOT NULL DEFAULT '',
    giro         TEXT NOT NULL DEFAULT '',
    direccion    TEXT NOT NULL DEFAULT '',
    ciudad       TEXT NOT NULL DEFAULT '',
    rep_legal    TEXT NOT NULL DEFAULT '',
    sucursal     TEXT NOT NULL DEFAULT '',
    honorarios   INTEGER NOT NULL DEFAULT 0,
    directorio   TEXT NOT NULL DEFAULT '',
    impuestos    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS periodo (
    id         INTEGER PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    ano        INTEGER NOT NULL,
    UNIQUE (empresa_id, ano)
);

CREATE TABLE IF NOT EXISTS cuenta (
    empresa_id INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    codigo     TEXT NOT NULL,
    nombre     TEXT NOT NULL DEFAULT '',
    cdocum     INTEGER NOT NULL DEFAULT 0,      -- 1 = pide documento de compra
    PRIMARY KEY (empresa_id, codigo)
);

CREATE TABLE IF NOT EXISTS ccosto (
    empresa_id INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    codigo     TEXT NOT NULL,
    nombre     TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (empresa_id, codigo)
);

CREATE TABLE IF NOT EXISTS proveedor (
    empresa_id INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    rut        TEXT NOT NULL,
    nombre     TEXT NOT NULL DEFAULT '',
    direccion  TEXT NOT NULL DEFAULT '',
    ciudad     TEXT NOT NULL DEFAULT '',
    giro       TEXT NOT NULL DEFAULT '',
    telefono   TEXT NOT NULL DEFAULT '',
    email      TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (empresa_id, rut)
);

CREATE TABLE IF NOT EXISTS asiento (
    id         INTEGER PRIMARY KEY,
    periodo_id INTEGER NOT NULL REFERENCES periodo(id) ON DELETE CASCADE,
    numero     INTEGER NOT NULL,
    tipo       TEXT NOT NULL DEFAULT 'T',      -- I Ingreso / E Egreso / T Traspaso
    fecha      TEXT,                           -- ISO aaaa-mm-dd
    glosa      TEXT NOT NULL DEFAULT '',
    debe       INTEGER NOT NULL DEFAULT 0,
    haber      INTEGER NOT NULL DEFAULT 0,
    cdcosto    TEXT NOT NULL DEFAULT '',
    UNIQUE (periodo_id, numero)
);
CREATE INDEX IF NOT EXISTS ix_asiento_fecha ON asiento(periodo_id, fecha, numero);
CREATE INDEX IF NOT EXISTS ix_asiento_tipo  ON asiento(periodo_id, tipo, fecha, numero);

CREATE TABLE IF NOT EXISTS detalle (
    id         INTEGER PRIMARY KEY,
    asiento_id INTEGER NOT NULL REFERENCES asiento(id) ON DELETE CASCADE,
    linea      INTEGER NOT NULL DEFAULT 0,
    codigo     TEXT NOT NULL,
    debe       INTEGER NOT NULL DEFAULT 0,
    haber      INTEGER NOT NULL DEFAULT 0,
    fecha      TEXT
);
CREATE INDEX IF NOT EXISTS ix_detalle_asiento ON detalle(asiento_id, linea);
CREATE INDEX IF NOT EXISTS ix_detalle_codigo  ON detalle(codigo, fecha);

CREATE TABLE IF NOT EXISTS compra (
    id          INTEGER PRIMARY KEY,
    detalle_id  INTEGER NOT NULL UNIQUE REFERENCES detalle(id) ON DELETE CASCADE,
    tdocum      INTEGER NOT NULL DEFAULT 1,
    fecha_doc   TEXT,
    numero_doc  INTEGER NOT NULL DEFAULT 0,
    rut_prov    TEXT NOT NULL DEFAULT '',
    neto        INTEGER NOT NULL DEFAULT 0,
    iva         INTEGER NOT NULL DEFAULT 0,
    adicional   INTEGER NOT NULL DEFAULT 0,
    total       INTEGER NOT NULL DEFAULT 0,
    cdcosto     TEXT NOT NULL DEFAULT '',
    detalle     TEXT NOT NULL DEFAULT '',
    fecha_pago  TEXT
);

CREATE TABLE IF NOT EXISTS usuario (
    usuario    TEXT PRIMARY KEY,
    nombre     TEXT NOT NULL DEFAULT '',
    clave_hash TEXT NOT NULL,
    nivel      TEXT NOT NULL DEFAULT '0000100000',
    es_admin   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS parametro (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
"""

# Usuarios que el original tenía "fijos" en el código (BrowUsuar en CONTAB.PRG).
# Aquí se crean como usuarios normales para que se puedan cambiar o borrar.
USUARIOS_INICIALES = [
    ("ADMIN", "ADMINISTRADOR", "ADMIN", True),
    ("CAC", "CLAUDIO COFRE V", "CAC", True),
    ("CONTA", "CONTABILIDAD", "CONTA", False),
]


def hash_clave(clave: str, sal: str | None = None) -> str:
    sal = sal or secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", clave.strip().upper().encode("utf-8"),
                            sal.encode("ascii"), 60000).hex()
    return f"{sal}${h}"


def verificar_clave(clave: str, guardado: str) -> bool:
    try:
        sal, _ = guardado.split("$", 1)
    except ValueError:
        return False
    return secrets.compare_digest(hash_clave(clave, sal), guardado)


class ErrorDatos(Exception):
    """Error de validación de datos que se muestra al usuario."""


class Database:
    def __init__(self, ruta: str):
        self.ruta = ruta
        nuevo = not os.path.exists(ruta)
        os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
        self.con = sqlite3.connect(ruta)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(SCHEMA)
        if nuevo or not self.con.execute("SELECT 1 FROM usuario LIMIT 1").fetchone():
            for u, n, c, a in USUARIOS_INICIALES:
                self.con.execute(
                    "INSERT OR IGNORE INTO usuario(usuario,nombre,clave_hash,es_admin) VALUES (?,?,?,?)",
                    (u, n, hash_clave(c), int(a)))
        self.con.commit()

    def close(self):
        self.con.close()

    @contextmanager
    def transaccion(self):
        try:
            yield self.con
            self.con.commit()
        except Exception:
            self.con.rollback()
            raise

    def q(self, sql: str, params=()) -> list[sqlite3.Row]:
        return self.con.execute(sql, params).fetchall()

    def q1(self, sql: str, params=()):
        return self.con.execute(sql, params).fetchone()

    def respaldar(self, destino: str) -> str:
        """Copia consistente de la base (opción Útiles > Respaldar)."""
        self.con.commit()
        dst = sqlite3.connect(destino)
        with dst:
            self.con.backup(dst)
        dst.close()
        return destino

    # ------------------------------------------------------------------ usuarios
    def usuarios(self):
        return self.q("SELECT usuario, nombre, nivel, es_admin FROM usuario ORDER BY usuario")

    def usuario(self, usuario: str):
        return self.q1("SELECT * FROM usuario WHERE usuario=?", (usuario.strip().upper(),))

    def login(self, usuario: str, clave: str):
        u = self.usuario(usuario)
        if u and verificar_clave(clave, u["clave_hash"]):
            return u
        return None

    def guardar_usuario(self, usuario: str, nombre: str, clave: str | None,
                        es_admin: bool = False, nuevo: bool = False):
        usuario = usuario.strip().upper()
        if not usuario:
            raise ErrorDatos("Debe ingresar el nombre de usuario.")
        if not nombre.strip():
            raise ErrorDatos("Debe ingresar el nombre.")
        with self.transaccion() as c:
            if nuevo:
                if self.usuario(usuario):
                    raise ErrorDatos("Ya existe este nombre de USUARIO.")
                if not clave:
                    raise ErrorDatos("Debe ingresar una clave.")
                c.execute("INSERT INTO usuario(usuario,nombre,clave_hash,es_admin) VALUES (?,?,?,?)",
                          (usuario, nombre.strip().upper(), hash_clave(clave), int(es_admin)))
            else:
                c.execute("UPDATE usuario SET nombre=?, es_admin=? WHERE usuario=?",
                          (nombre.strip().upper(), int(es_admin), usuario))
                if clave:
                    c.execute("UPDATE usuario SET clave_hash=? WHERE usuario=?",
                              (hash_clave(clave), usuario))

    def borrar_usuario(self, usuario: str):
        admins = self.q1("SELECT COUNT(*) n FROM usuario WHERE es_admin=1 AND usuario<>?", (usuario,))["n"]
        u = self.usuario(usuario)
        if u and u["es_admin"] and admins == 0:
            raise ErrorDatos("No se puede eliminar el último usuario administrador.")
        with self.transaccion() as c:
            c.execute("DELETE FROM usuario WHERE usuario=?", (usuario,))

    # ------------------------------------------------------------------ empresas
    def empresas(self, orden: str = "razon_social"):
        orden = orden if orden in ("rut", "razon_social", "directorio") else "razon_social"
        return self.q(f"SELECT * FROM empresa ORDER BY {orden}")

    def empresa(self, empresa_id: int):
        return self.q1("SELECT * FROM empresa WHERE id=?", (empresa_id,))

    def empresa_por_rut(self, rut: str):
        return self.q1("SELECT * FROM empresa WHERE rut=?", (util.limpiar_rut(rut),))

    def guardar_empresa(self, datos: dict, empresa_id: int | None = None,
                        ano_inicial: int | None = None) -> int:
        rut = util.limpiar_rut(datos.get("rut"))
        if empresa_id is None:
            if not util.validar_rut(rut):
                raise ErrorDatos("Error en el dígito verificador del R.U.T.")
            if self.empresa_por_rut(rut):
                raise ErrorDatos("Esta Empresa ya existe.")
            directorio = (datos.get("directorio") or "").strip().upper()
            if not directorio:
                raise ErrorDatos("Debe indicar el directorio (código corto) de la empresa.")
            if self.q1("SELECT 1 FROM empresa WHERE directorio=?", (directorio,)):
                raise ErrorDatos(f"El Directorio {directorio} ya existe.")
        campos = ["razon_social", "giro", "direccion", "ciudad", "rep_legal", "sucursal"]
        valores = [str(datos.get(k, "") or "").strip().upper() for k in campos]
        honor = int(datos.get("honorarios") or 0)
        with self.transaccion() as c:
            if empresa_id is None:
                cur = c.execute(
                    "INSERT INTO empresa(rut,razon_social,giro,direccion,ciudad,rep_legal,sucursal,"
                    "honorarios,directorio) VALUES (?,?,?,?,?,?,?,?,?)",
                    [rut, *valores, honor, (datos.get("directorio") or "").strip().upper()])
                empresa_id = cur.lastrowid
                if ano_inicial:
                    c.execute("INSERT INTO periodo(empresa_id, ano) VALUES (?,?)", (empresa_id, ano_inicial))
            else:
                c.execute(
                    "UPDATE empresa SET razon_social=?,giro=?,direccion=?,ciudad=?,rep_legal=?,"
                    "sucursal=?,honorarios=? WHERE id=?", [*valores, honor, empresa_id])
        return empresa_id

    def borrar_empresa(self, empresa_id: int):
        with self.transaccion() as c:
            c.execute("DELETE FROM empresa WHERE id=?", (empresa_id,))

    def resumen_empresa(self, empresa_id: int) -> dict:
        r = self.q1("""SELECT (SELECT COUNT(*) FROM periodo WHERE empresa_id=:e) periodos,
                              (SELECT COUNT(*) FROM asiento a JOIN periodo p ON p.id=a.periodo_id
                                WHERE p.empresa_id=:e) asientos""", {"e": empresa_id})
        return dict(r)

    # ------------------------------------------------------------------ periodos
    def periodos(self, empresa_id: int):
        return self.q("SELECT * FROM periodo WHERE empresa_id=? ORDER BY ano", (empresa_id,))

    def periodo(self, periodo_id: int):
        return self.q1("SELECT * FROM periodo WHERE id=?", (periodo_id,))

    def crear_periodo(self, empresa_id: int, ano: int) -> int:
        if ano < 1980 or ano > 2200:
            raise ErrorDatos("Año inválido.")
        if self.q1("SELECT 1 FROM periodo WHERE empresa_id=? AND ano=?", (empresa_id, ano)):
            raise ErrorDatos(f"El año {ano} ya existe para esta empresa.")
        with self.transaccion() as c:
            return c.execute("INSERT INTO periodo(empresa_id, ano) VALUES (?,?)", (empresa_id, ano)).lastrowid

    # ------------------------------------------------------------------ cuentas
    def cuentas(self, empresa_id: int, orden: str = "codigo"):
        orden = "nombre" if orden == "nombre" else "codigo"
        return self.q(f"SELECT * FROM cuenta WHERE empresa_id=? ORDER BY {orden}", (empresa_id,))

    def cuenta(self, empresa_id: int, codigo: str):
        return self.q1("SELECT * FROM cuenta WHERE empresa_id=? AND codigo=?", (empresa_id, codigo))

    def nombre_cuenta(self, empresa_id: int, codigo: str) -> str:
        r = self.cuenta(empresa_id, codigo)
        return r["nombre"] if r else ""

    def guardar_cuenta(self, empresa_id: int, codigo: str, nombre: str, cdocum: bool, nuevo: bool):
        codigo = util.limpiar_codigo(codigo)
        if len(codigo) != 6 or not codigo.isdigit():
            raise ErrorDatos("El código de cuenta debe tener 6 dígitos (99.99.99).")
        with self.transaccion() as c:
            if nuevo:
                if self.cuenta(empresa_id, codigo):
                    raise ErrorDatos("Esta Cuenta ya existe.")
                c.execute("INSERT INTO cuenta(empresa_id,codigo,nombre,cdocum) VALUES (?,?,?,?)",
                          (empresa_id, codigo, nombre.strip().upper(), int(bool(cdocum))))
            else:
                c.execute("UPDATE cuenta SET nombre=?, cdocum=? WHERE empresa_id=? AND codigo=?",
                          (nombre.strip().upper(), int(bool(cdocum)), empresa_id, codigo))

    def uso_cuenta(self, empresa_id: int, codigo: str) -> int:
        return self.q1("""SELECT COUNT(*) n FROM detalle d JOIN asiento a ON a.id=d.asiento_id
                          JOIN periodo p ON p.id=a.periodo_id
                          WHERE p.empresa_id=? AND d.codigo=?""", (empresa_id, codigo))["n"]

    def borrar_cuenta(self, empresa_id: int, codigo: str):
        n = self.uso_cuenta(empresa_id, codigo)
        if n:
            raise ErrorDatos(f"La cuenta tiene {n} movimientos en asientos; no se puede borrar.")
        with self.transaccion() as c:
            c.execute("DELETE FROM cuenta WHERE empresa_id=? AND codigo=?", (empresa_id, codigo))

    # ------------------------------------------------------------------ centros de costo
    def ccostos(self, empresa_id: int, orden: str = "codigo"):
        orden = "nombre" if orden == "nombre" else "codigo"
        return self.q(f"SELECT * FROM ccosto WHERE empresa_id=? ORDER BY {orden}", (empresa_id,))

    def ccosto(self, empresa_id: int, codigo: str):
        return self.q1("SELECT * FROM ccosto WHERE empresa_id=? AND codigo=?", (empresa_id, codigo))

    def nombre_ccosto(self, empresa_id: int, codigo: str) -> str:
        r = self.ccosto(empresa_id, codigo) if codigo else None
        return r["nombre"] if r else ""

    def guardar_ccosto(self, empresa_id: int, codigo: str, nombre: str, nuevo: bool):
        codigo = (codigo or "").strip().upper()[:6]
        if not codigo:
            raise ErrorDatos("Debe ingresar el código.")
        with self.transaccion() as c:
            if nuevo:
                if self.ccosto(empresa_id, codigo):
                    raise ErrorDatos("Este C. de Costo ya existe.")
                c.execute("INSERT INTO ccosto(empresa_id,codigo,nombre) VALUES (?,?,?)",
                          (empresa_id, codigo, nombre.strip().upper()))
            else:
                c.execute("UPDATE ccosto SET nombre=? WHERE empresa_id=? AND codigo=?",
                          (nombre.strip().upper(), empresa_id, codigo))

    def borrar_ccosto(self, empresa_id: int, codigo: str):
        with self.transaccion() as c:
            c.execute("DELETE FROM ccosto WHERE empresa_id=? AND codigo=?", (empresa_id, codigo))

    # ------------------------------------------------------------------ proveedores
    def proveedores(self, empresa_id: int, orden: str = "rut"):
        orden = "nombre" if orden == "nombre" else "rut"
        return self.q(f"SELECT * FROM proveedor WHERE empresa_id=? ORDER BY {orden}", (empresa_id,))

    def proveedor(self, empresa_id: int, rut: str):
        return self.q1("SELECT * FROM proveedor WHERE empresa_id=? AND rut=?",
                       (empresa_id, util.limpiar_rut(rut)))

    def nombre_proveedor(self, empresa_id: int, rut: str) -> str:
        r = self.proveedor(empresa_id, rut) if rut else None
        return r["nombre"] if r else ""

    def guardar_proveedor(self, empresa_id: int, datos: dict, nuevo: bool):
        rut = util.limpiar_rut(datos.get("rut"))
        if nuevo:
            if not util.validar_rut(rut):
                raise ErrorDatos("Error en el dígito verificador del R.U.T.")
            if self.proveedor(empresa_id, rut):
                raise ErrorDatos("Este PROVEEDOR ya existe.")
        campos = ["nombre", "direccion", "ciudad", "giro", "telefono", "email"]
        vals = [str(datos.get(k, "") or "").strip() for k in campos]
        vals[0] = vals[0].upper()
        with self.transaccion() as c:
            if nuevo:
                c.execute("INSERT INTO proveedor(empresa_id,rut,nombre,direccion,ciudad,giro,telefono,email)"
                          " VALUES (?,?,?,?,?,?,?,?)", [empresa_id, rut, *vals])
            else:
                c.execute("UPDATE proveedor SET nombre=?,direccion=?,ciudad=?,giro=?,telefono=?,email=?"
                          " WHERE empresa_id=? AND rut=?", [*vals, empresa_id, rut])

    def borrar_proveedor(self, empresa_id: int, rut: str):
        with self.transaccion() as c:
            c.execute("DELETE FROM proveedor WHERE empresa_id=? AND rut=?", (empresa_id, util.limpiar_rut(rut)))

    # ------------------------------------------------------------------ asientos
    def asientos(self, periodo_id: int, orden: str = "numero"):
        ordenes = {"numero": "numero", "fecha": "fecha, numero", "tipo": "tipo, fecha, numero"}
        return self.q(f"SELECT * FROM asiento WHERE periodo_id=? ORDER BY {ordenes.get(orden, 'numero')}",
                      (periodo_id,))

    def asiento(self, asiento_id: int):
        return self.q1("SELECT * FROM asiento WHERE id=?", (asiento_id,))

    def rango_fechas(self, periodo_id: int):
        r = self.q1("SELECT MIN(fecha) d, MAX(fecha) h FROM asiento WHERE periodo_id=? AND fecha IS NOT NULL",
                    (periodo_id,))
        return (util.from_iso(r["d"]), util.from_iso(r["h"])) if r and r["d"] else (None, None)

    def detalle_asiento(self, asiento_id: int) -> list[dict]:
        """Líneas del asiento con su documento de compra (si tiene)."""
        filas = self.q("""SELECT d.id detalle_id, d.linea, d.codigo, d.debe, d.haber, d.fecha,
                                 c.tdocum, c.fecha_doc, c.numero_doc, c.rut_prov, c.neto, c.iva,
                                 c.adicional, c.total, c.cdcosto c_cdcosto, c.detalle c_detalle,
                                 c.fecha_pago, c.id compra_id
                          FROM detalle d LEFT JOIN compra c ON c.detalle_id=d.id
                          WHERE d.asiento_id=? ORDER BY d.linea, d.id""", (asiento_id,))
        res = []
        for f in filas:
            linea = {"codigo": f["codigo"], "debe": f["debe"], "haber": f["haber"], "documento": None}
            if f["compra_id"]:
                linea["documento"] = {
                    "tdocum": f["tdocum"], "fecha_doc": f["fecha_doc"], "numero_doc": f["numero_doc"],
                    "rut_prov": f["rut_prov"], "neto": f["neto"], "iva": f["iva"],
                    "adicional": f["adicional"], "total": f["total"], "cdcosto": f["c_cdcosto"],
                    "detalle": f["c_detalle"], "fecha_pago": f["fecha_pago"]}
            res.append(linea)
        return res

    def siguiente_numero(self, periodo_id: int) -> int:
        return (self.q1("SELECT MAX(numero) m FROM asiento WHERE periodo_id=?", (periodo_id,))["m"] or 0) + 1

    def guardar_asiento(self, periodo_id: int, cab: dict, lineas: list[dict],
                        asiento_id: int | None = None) -> int:
        """GAsien(): valida cuadratura y graba cabecera + detalle + compras.

        cab: tipo, fecha (date/ISO), glosa, cdcosto
        lineas: [{codigo, debe, haber, documento: dict|None}]
        """
        tot_debe = sum(int(l.get("debe") or 0) for l in lineas)
        tot_haber = sum(int(l.get("haber") or 0) for l in lineas)
        if tot_debe != tot_haber:
            raise ErrorDatos("Las sumas del comprobante no están cuadradas.\nRevise e inténtelo nuevamente.")
        if not lineas:
            raise ErrorDatos("El asiento no tiene líneas de detalle.")
        tipo = (cab.get("tipo") or "").upper()
        if tipo not in util.TIPOS_ASIENTO:
            raise ErrorDatos("El tipo de asiento debe ser I (Ingreso), E (Egreso) o T (Traspaso).")
        fecha = util.to_iso(cab.get("fecha"))
        if not fecha:
            raise ErrorDatos("Debe ingresar la fecha.")
        glosa = (cab.get("glosa") or "").strip().upper()
        if not glosa:
            raise ErrorDatos("Debe ingresar la glosa.")
        cdcosto = (cab.get("cdcosto") or "").strip().upper()
        with self.transaccion() as c:
            if asiento_id is None:
                numero = cab.get("numero") or self.siguiente_numero(periodo_id)
                asiento_id = c.execute(
                    "INSERT INTO asiento(periodo_id,numero,tipo,fecha,glosa,debe,haber,cdcosto)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (periodo_id, numero, tipo, fecha, glosa, tot_debe, tot_haber, cdcosto)).lastrowid
            else:
                c.execute("UPDATE asiento SET tipo=?,fecha=?,glosa=?,debe=?,haber=?,cdcosto=? WHERE id=?",
                          (tipo, fecha, glosa, tot_debe, tot_haber, cdcosto, asiento_id))
                c.execute("DELETE FROM detalle WHERE asiento_id=?", (asiento_id,))
            for i, l in enumerate(lineas, 1):
                det_id = c.execute(
                    "INSERT INTO detalle(asiento_id,linea,codigo,debe,haber,fecha) VALUES (?,?,?,?,?,?)",
                    (asiento_id, i, l["codigo"], int(l.get("debe") or 0), int(l.get("haber") or 0),
                     fecha)).lastrowid
                d = l.get("documento")
                if d and int(d.get("numero_doc") or 0) != 0:
                    c.execute(
                        "INSERT INTO compra(detalle_id,tdocum,fecha_doc,numero_doc,rut_prov,neto,iva,"
                        "adicional,total,cdcosto,detalle,fecha_pago) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (det_id, int(d.get("tdocum") or 1), util.to_iso(d.get("fecha_doc")),
                         int(d.get("numero_doc") or 0), util.limpiar_rut(d.get("rut_prov")),
                         int(d.get("neto") or 0), int(d.get("iva") or 0), int(d.get("adicional") or 0),
                         int(d.get("total") or 0), (d.get("cdcosto") or cdcosto or "").strip().upper(),
                         (d.get("detalle") or "").strip().upper(), util.to_iso(d.get("fecha_pago"))))
        return asiento_id

    def borrar_asiento(self, asiento_id: int):
        with self.transaccion() as c:
            c.execute("DELETE FROM asiento WHERE id=?", (asiento_id,))

    # ------------------------------------------------------------------ consultas para informes
    def movimientos(self, periodo_id: int, codigo: str | None = None, desde=None, hasta=None):
        sql = ["""SELECT d.codigo, d.debe, d.haber, a.fecha, a.numero, a.glosa, a.tipo
                  FROM detalle d JOIN asiento a ON a.id=d.asiento_id WHERE a.periodo_id=?"""]
        p: list = [periodo_id]
        if codigo:
            sql.append("AND d.codigo=?"); p.append(codigo)
        if desde:
            sql.append("AND a.fecha>=?"); p.append(util.to_iso(desde))
        if hasta:
            sql.append("AND a.fecha<=?"); p.append(util.to_iso(hasta))
        sql.append("ORDER BY d.codigo, a.fecha, a.numero, d.linea")
        return self.q(" ".join(sql), p)

    def compras(self, periodo_id: int, desde=None, hasta=None, cdcosto: str | None = None):
        sql = ["""SELECT c.*, a.numero nasiento, a.fecha fecha_asiento, d.codigo ccuenta
                  FROM compra c JOIN detalle d ON d.id=c.detalle_id
                  JOIN asiento a ON a.id=d.asiento_id WHERE a.periodo_id=?"""]
        p: list = [periodo_id]
        if desde:
            sql.append("AND c.fecha_doc>=?"); p.append(util.to_iso(desde))
        if hasta:
            sql.append("AND c.fecha_doc<=?"); p.append(util.to_iso(hasta))
        if cdcosto is not None:
            sql.append("AND c.cdcosto=?"); p.append(cdcosto)
        sql.append("ORDER BY c.cdcosto, c.fecha_doc, a.numero")
        return self.q(" ".join(sql), p)

    def rango_fechas_compras(self, periodo_id: int):
        r = self.q1("""SELECT MIN(c.fecha_doc) d, MAX(c.fecha_doc) h FROM compra c
                       JOIN detalle d ON d.id=c.detalle_id JOIN asiento a ON a.id=d.asiento_id
                       WHERE a.periodo_id=?""", (periodo_id,))
        return (util.from_iso(r["d"]), util.from_iso(r["h"])) if r and r["d"] else (None, None)


def nombre_respaldo(ruta_db: str) -> str:
    base, ext = os.path.splitext(os.path.basename(ruta_db))
    sello = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base}_respaldo_{sello}{ext or '.db'}"


def copiar_archivo(origen: str, destino: str):
    shutil.copy2(origen, destino)
