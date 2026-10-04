"""Importador de datos del ContaWin original (archivos DBF) a SQLite.

Uso desde la línea de comandos:

    python -m contawin.importer "D:\\Respaldar 24-01-2023\\d Disco C\\CONTAWIN"  [contawin.db]  [--reemplazar] [--cp850]

También se usa desde el menú Útiles > Importar datos DBF.

Recorre:
    <raíz>\\EMPRESA.DBF
    <raíz>\\<DIRECTORIO>\\CUENTAS.DBF, CCOSTO.DBF, RESPAL.DBF
    <raíz>\\<DIRECTORIO>\\TRAaaaa\\ASIENTOS.DBF, DETASIEN.DBF, COMPRAS.DBF, PROVEE.DBF

Los registros marcados como borrados en los DBF no se importan
(igual que SET DELETED ON en el programa original).
"""
from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field

from . import util
from .db import Database
from .dbf_reader import buscar_archivo, buscar_carpeta, leer


@dataclass
class Resultado:
    empresas: int = 0
    omitidas: int = 0
    periodos: int = 0
    cuentas: int = 0
    ccostos: int = 0
    proveedores: int = 0
    asientos: int = 0
    lineas: int = 0
    compras: int = 0
    avisos: list[str] = field(default_factory=list)

    def resumen(self) -> str:
        t = (f"Empresas importadas: {self.empresas}"
             + (f"  (omitidas por existir: {self.omitidas})" if self.omitidas else "")
             + f"\nAños: {self.periodos}\nCuentas: {self.cuentas}\nCentros de costo: {self.ccostos}"
             f"\nProveedores: {self.proveedores}\nAsientos: {self.asientos}"
             f"\nLíneas de detalle: {self.lineas}\nDocumentos de compra: {self.compras}")
        if self.avisos:
            t += f"\n\nAvisos ({len(self.avisos)}):\n- " + "\n- ".join(self.avisos[:60])
            if len(self.avisos) > 60:
                t += f"\n... y {len(self.avisos) - 60} más"
        return t


def _s(v) -> str:
    return str(v or "").strip()


def _i(v) -> int:
    try:
        return int(round(float(v or 0)))
    except (TypeError, ValueError):
        return 0


def anos_disponibles(carpeta_empresa: str, encoding: str = "cp1252") -> list[int]:
    anos = set()
    for r in leer(carpeta_empresa, "RESPAL.DBF", encoding):
        a = _i(r.get("ANO"))
        if a:
            anos.add(a)
    if os.path.isdir(carpeta_empresa):
        for f in os.listdir(carpeta_empresa):
            m = re.fullmatch(r"TRA(\d{4})", f, re.IGNORECASE)
            if m and os.path.isdir(os.path.join(carpeta_empresa, f)):
                anos.add(int(m[1]))
    return sorted(anos)


def importar(raiz: str, db: Database, reemplazar: bool = False, progreso=None,
             encoding: str = "cp1252") -> Resultado:
    """Importa todas las empresas encontradas en la carpeta raíz de ContaWin.

    progreso: función opcional progreso(texto) para informar avance.
    encoding: cp1252 (ContaWin Windows) o cp850 (datos de la versión DOS).
    """
    res = Resultado()
    archivo_emp = buscar_archivo(raiz, "EMPRESA.DBF")
    if not archivo_emp:
        raise FileNotFoundError(f"No se encontró EMPRESA.DBF en:\n{raiz}")
    empresas = leer(raiz, "EMPRESA.DBF", encoding)

    for e in empresas:
        rut = util.limpiar_rut(e.get("RUT"))
        directorio = _s(e.get("DIRECTORIO")).upper()
        nombre = _s(e.get("RAZONSOC"))
        if not rut:
            res.avisos.append(f"Empresa sin RUT omitida: {nombre}")
            continue
        if progreso:
            progreso(f"Importando {nombre} ...")
        existente = db.empresa_por_rut(rut)
        if existente:
            if not reemplazar:
                res.omitidas += 1
                res.avisos.append(f"{nombre}: ya existe en la base (RUT {util.formato_rut(rut)}), no se importó.")
                continue
            db.borrar_empresa(existente["id"])

        carpeta = buscar_carpeta(raiz, directorio) if directorio else None
        if not carpeta:
            res.avisos.append(f"{nombre}: no se encontró la carpeta '{directorio}'; se importa solo la ficha.")

        with db.transaccion() as c:
            emp_id = c.execute(
                "INSERT INTO empresa(rut,razon_social,giro,direccion,ciudad,rep_legal,sucursal,"
                "honorarios,directorio,impuestos) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (rut, nombre, _s(e.get("GIRO")), _s(e.get("DIRECCION")), _s(e.get("CIUDAD")),
                 _s(e.get("REPLEGAL")), _s(e.get("SUCURSAL")), _i(e.get("HONORARIOS")),
                 directorio, _i(e.get("IMPUESTOS")))).lastrowid
            res.empresas += 1
            if not carpeta:
                continue

            # --- plan de cuentas
            vistos = set()
            for r in leer(carpeta, "CUENTAS.DBF", encoding):
                cod = _s(r.get("CODIGO")).upper()
                if not cod or cod in vistos:
                    continue
                vistos.add(cod)
                c.execute("INSERT INTO cuenta(empresa_id,codigo,nombre,cdocum) VALUES (?,?,?,?)",
                          (emp_id, cod, _s(r.get("NOMBRE")), 1 if _i(r.get("CDOCUM")) == 1 else 0))
                res.cuentas += 1

            # --- centros de costo
            vistos = set()
            for r in leer(carpeta, "CCOSTO.DBF", encoding):
                cod = _s(r.get("CODIGO")).upper()
                if not cod or cod in vistos:
                    continue
                vistos.add(cod)
                c.execute("INSERT INTO ccosto(empresa_id,codigo,nombre) VALUES (?,?,?)",
                          (emp_id, cod, _s(r.get("NOMBRE"))))
                res.ccostos += 1

            # --- años
            proveedores: dict[str, dict] = {}
            for ano in anos_disponibles(carpeta, encoding):
                per_id = c.execute("INSERT INTO periodo(empresa_id,ano) VALUES (?,?)", (emp_id, ano)).lastrowid
                res.periodos += 1
                cy = buscar_carpeta(carpeta, f"TRA{ano:04d}")
                if not cy:
                    continue

                for r in leer(cy, "PROVEE.DBF", encoding):
                    rp = util.limpiar_rut(r.get("RUT"))
                    if rp:
                        proveedores[rp] = r          # el año más reciente prevalece

                # asientos
                id_por_numero: dict[int, int] = {}
                fecha_por_numero: dict[int, str | None] = {}
                for r in leer(cy, "ASIENTOS.DBF", encoding):
                    num = _i(r.get("NUMERO"))
                    if num in id_por_numero:
                        res.avisos.append(f"{nombre} {ano}: asiento N° {num} duplicado; se conserva el primero.")
                        continue
                    tipo = _s(r.get("TIPO")).upper() or "T"
                    fecha = util.to_iso(r.get("FECHA"))
                    aid = c.execute(
                        "INSERT INTO asiento(periodo_id,numero,tipo,fecha,glosa,debe,haber,cdcosto)"
                        " VALUES (?,?,?,?,?,?,?,?)",
                        (per_id, num, tipo, fecha, _s(r.get("GLOSA")), _i(r.get("DEBE")),
                         _i(r.get("HABER")), _s(r.get("CDCOSTO")).upper())).lastrowid
                    id_por_numero[num] = aid
                    fecha_por_numero[num] = fecha
                    res.asientos += 1

                # detalle
                lineas_por_asiento: dict[int, list[tuple[int, str]]] = defaultdict(list)
                sumas: dict[int, list[int]] = defaultdict(lambda: [0, 0])
                huerfanas = 0
                for r in leer(cy, "DETASIEN.DBF", encoding):
                    num = _i(r.get("NUMERO"))
                    aid = id_por_numero.get(num)
                    if not aid:
                        huerfanas += 1
                        continue
                    cod = _s(r.get("CODIGO")).upper()
                    debe, haber = _i(r.get("DEBE")), _i(r.get("HABER"))
                    n_linea = len(lineas_por_asiento[num]) + 1
                    did = c.execute(
                        "INSERT INTO detalle(asiento_id,linea,codigo,debe,haber,fecha) VALUES (?,?,?,?,?,?)",
                        (aid, n_linea, cod, debe, haber,
                         util.to_iso(r.get("FECHA")) or fecha_por_numero.get(num))).lastrowid
                    lineas_por_asiento[num].append((did, cod))
                    sumas[num][0] += debe
                    sumas[num][1] += haber
                    res.lineas += 1
                if huerfanas:
                    res.avisos.append(f"{nombre} {ano}: {huerfanas} líneas de detalle sin asiento (omitidas).")
                for num, aid in id_por_numero.items():
                    d, h = sumas.get(num, [0, 0])
                    if d != h:
                        res.avisos.append(f"{nombre} {ano}: asiento N° {num} descuadrado (debe {util.fmt_monto(d)}"
                                          f" / haber {util.fmt_monto(h)}).")
                    c.execute("UPDATE asiento SET debe=?, haber=? WHERE id=?", (d, h, aid))

                # compras (ligadas a la línea con la misma cuenta, como el SEEK numero+cuenta original)
                usados: set[int] = set()
                for r in leer(cy, "COMPRAS.DBF", encoding):
                    num = _i(r.get("NASIENTO"))
                    cta = _s(r.get("CCUENTA")).upper()
                    candidatos = [did for did, cod in lineas_por_asiento.get(num, [])
                                  if cod == cta and did not in usados]
                    if not candidatos:
                        res.avisos.append(f"{nombre} {ano}: documento N° {_i(r.get('NUMEROC'))} del asiento "
                                          f"{num} sin línea de cuenta {util.formato_codigo(cta)} (omitido).")
                        continue
                    did = candidatos[0]
                    usados.add(did)
                    td = _i(r.get("TDOCUM")) or 1
                    c.execute(
                        "INSERT INTO compra(detalle_id,tdocum,fecha_doc,numero_doc,rut_prov,neto,iva,adicional,"
                        "total,cdcosto,detalle,fecha_pago) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (did, td, util.to_iso(r.get("FECHAD")), _i(r.get("NUMEROC")),
                         util.limpiar_rut(r.get("RPROVEE")), _i(r.get("NETO")), _i(r.get("IVA")),
                         _i(r.get("ADICIONAL")), _i(r.get("TOTAL")), _s(r.get("CDCOSTO")).upper(),
                         _s(r.get("DETALLE")), util.to_iso(r.get("FECPAGO"))))
                    res.compras += 1

            for rp, r in proveedores.items():
                c.execute("INSERT INTO proveedor(empresa_id,rut,nombre,direccion,ciudad,giro,telefono,email)"
                          " VALUES (?,?,?,?,?,?,?,?)",
                          (emp_id, rp, _s(r.get("NOMBRE")), _s(r.get("DIRECC")), _s(r.get("CIUDAD")),
                           _s(r.get("GIRO")), _s(r.get("TELEFONO")), _s(r.get("EMAIL"))))
                res.proveedores += 1

    res.avisos.append("Los usuarios del sistema antiguo no se importan (sus claves están cifradas "
                      "con FiveWin). Use Útiles > Usuarios para crearlos de nuevo.")
    return res


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    reemplazar = "--reemplazar" in argv
    encoding = "cp850" if "--cp850" in argv else "cp1252"
    argv = [a for a in argv if a not in ("--reemplazar", "--cp850")]
    if not argv:
        print(__doc__)
        return 1
    raiz = argv[0]
    ruta_db = argv[1] if len(argv) > 1 else os.path.join(os.getcwd(), "contawin.db")
    db = Database(ruta_db)
    try:
        res = importar(raiz, db, reemplazar, progreso=print, encoding=encoding)
    finally:
        db.close()
    print()
    print(res.resumen())
    print(f"\nBase de datos: {ruta_db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
