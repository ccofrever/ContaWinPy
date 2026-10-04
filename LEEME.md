# ContaWin para Python

Traspaso del **Sistema de Contabilidad ContaWin** (xHarbour + FiveWin, datos en DBF)
a **Python 3 + PySide6 (Qt)**, con los datos en un único archivo **SQLite**.

## Instalación (Windows)

1. Instale Python 3.10 o superior desde <https://www.python.org/downloads/>
   (marque **"Add Python to PATH"** al instalar).
2. Haga doble clic en **`instalar.bat`** (instala PySide6 y openpyxl; solo la primera vez).
3. Inicie el sistema con **`ContaWin.bat`** (o `python main.py`).

Usuarios iniciales (cámbielos en *Útiles > Usuarios*):

| Usuario | Clave | Administrador |
|---------|-------|---------------|
| ADMIN   | ADMIN | Sí |
| CAC     | CAC   | Sí |
| CONTA   | CONTA | No |

## Traer los datos del ContaWin antiguo

La primera vez que entre, si la base está vacía, el sistema ofrece importar los DBF.
También está en **Útiles > Importar datos del ContaWin antiguo (DBF)…**: elija la carpeta
`CONTAWIN` (la que contiene `EMPRESA.DBF`). Si esta carpeta `ContaWinPy` está dentro de
`CONTAWIN`, el diálogo ya parte ahí.

Se importan, por cada empresa de `EMPRESA.DBF`: plan de cuentas, centros de costo,
todos los años (`TRAaaaa`), asientos con su detalle, documentos de compra y proveedores.
Los registros marcados como borrados en los DBF no se importan. Al final se muestra un
resumen con avisos (asientos descuadrados, documentos sin línea, etc.).

Desde la línea de comandos: `importar_dbf.bat` o

```
python -m contawin.importer "D:\ruta\CONTAWIN" datos\contawin.db [--reemplazar] [--cp850]
```

(`--cp850` solo si los datos vienen de la versión DOS).

**Los archivos DBF originales no se modifican**: el programa antiguo sigue funcionando.

## Equivalencias con el programa original

| Original (PRG) | Python |
|---|---|
| CONTAB.PRG – menú, barra, login, selección empresa/año | `ui/principal.py`, `ui/inicio.py` |
| MEMPRESA.PRG, MCUENTAS.PRG, MCCOSTO.PRG, MPROVEE.PRG, MUSUA.PRG | `ui/mantenedores.py` |
| ASIENTOS.PRG – comprobantes, detalle, documento de compra | `ui/asientos.py` |
| LIBRO.PRG / LIBROXT.PRG – libro diario (y por tipo) | `reports.libro_diario` |
| MAYOR.PRG – movimientos de mayor | `reports.libro_mayor` |
| BAL8WIN.PRG – balance 8 columnas | `reports.balance_8_columnas` |
| BALTI.PRG – balance tipo informe | `reports.balance_tipo_informe` |
| LIBROC.PRG – libro de compras (+ Excel) | `reports.libro_compras` |
| CREARDBF.PRG – estructura de tablas | `db.py` (esquema SQLite) |
| FUNCIONS.PRG – ValRut, Ver_Rut, VerCodigos… | `util.py` |
| PRINT … PREVIEW / REPORT / XLS | `ui/impresion.py` (vista previa, imprimir, PDF, Excel) |
| CONTAW.ini | `contawin.ini` |

Atajos: **F2** selecciona empresa, **F3** comprobantes, **F4** plan de cuentas, **Ctrl+N** nuevo comprobante;
en las grillas **Insert** = nuevo, **Supr** = borrar, **Enter**/doble clic = modificar;
en el asiento **Ctrl+S** = guardar.

## Diferencias y mejoras respecto al original

- **Usuarios**: las claves del `USUARIO.DBF` estaban cifradas con `Encrypt()` de FiveWin y no
  se pueden traer; se recrean (ver tabla de arriba). Los usuarios "fijos" que estaban escritos
  en el código ahora son usuarios normales, con clave guardada como hash.
- Se quitó la verificación anticopia (`c:\windows\confiwin.sys`).
- **Proveedores**: antes había un `PROVEE.DBF` por año; ahora son por empresa (compartidos entre años).
- **Asiento**: al agregar una línea se propone el monto que falta para cuadrar; se avisa si la
  fecha no corresponde al año de trabajo; una línea lleva monto en Debe *o* en Haber.
- **Documento de compra**: además del total se guardan Neto e IVA (cálculo automático del 19 %
  para facturas, notas de crédito y débito; editable) y se puede crear el proveedor en el momento.
- **Libro de compras**: muestra Neto, IVA y Total reales (el original imprimía el total en la
  columna neto) e incluye los documentos sin centro de costo.
- **Libro mayor**: muestra el saldo anterior (arrastre) antes de los movimientos y el saldo
  acumulado como Deudor (D) / Acreedor (A).
- **Balance 8 columnas**: agrega la constancia del Art. 100 del Código Tributario y las firmas.
- No se puede borrar una cuenta que tiene movimientos; borrar una empresa pide escribir su RUT.
- Todos los informes se pueden ver en pantalla, imprimir, guardar en PDF o pasar a Excel.
- *Útiles > Respaldar base de datos* guarda una copia de seguridad.

## Asiento de apertura

El asiento de apertura de cada año es el resultado del balance del año anterior
(*Ingresos > Asiento de apertura…*; también se ofrece al crear un año nuevo):

- Cuentas de balance (códigos 1 y 2): saldo deudor al Debe, saldo acreedor al Haber.
- Cuentas de resultado (3 y 4): se cierran; su diferencia (utilidad o pérdida del ejercicio)
  va a la cuenta de patrimonio que usted elija (utilidad al Haber, pérdida al Debe). La cuenta
  elegida se recuerda para los años siguientes.
- Se graba como comprobante N° 1 (si está libre), tipo Traspaso, fecha 01/01, glosa
  «ASIENTO DE APERTURA aaaa (SALDOS AL 31-12-aaaa)». Si después se corrige el año anterior,
  volver a generarla reemplaza el mismo asiento.
- Al crear un año se puede elegir «Crear el año sin apertura».

## Apariencia (sistema de diseño ContaWin)

La interfaz sigue el sistema de diseño **ContaWin**: fondo claro, petróleo (`brand`) solo para la
acción principal y la ubicación actual, montos en fuente monoespaciada alineados a la derecha,
estados con ícono + texto (✓ Cuadrado / ⚠ Descuadrado) y foco visible en todos los controles.

- **Ventana principal**: barra lateral con Ingresos, Informes, Compras y Utilidades; cabecera con
  empresa, año y usuario; tablero con estado del período, accesos rápidos y últimos comprobantes.
- **Tema**: *Útiles > Apariencia* (Claro, Oscuro o Según Windows), o `tema =` en `contawin.ini`.
  Se aplica al volver a abrir el programa.
- **Fuentes**: el sistema usa IBM Plex Sans / IBM Plex Mono. Para usarlas, copie los archivos
  `.ttf` en `contawin\fuentes\` (por ejemplo `IBMPlexSans-Regular.ttf`, `-Medium`, `-SemiBold` e
  `IBMPlexMono-Regular.ttf`, `-Medium`); si no están, se usan Segoe UI y Consolas.
- Los colores, tamaños e íconos están en `contawin/ui/tema.py`.

## Estructura

```
main.py                 inicio de la aplicación
contawin/
  db.py                 base de datos SQLite (esquema y operaciones)
  importer.py           importador desde los DBF
  dbf_reader.py         lector de DBF (sin dependencias)
  reports.py            cálculo de informes + exportación Excel/CSV
  util.py               RUT, códigos, montos, fechas, tipos de documento
  config.py             contawin.ini
  ui/                   pantallas PySide6 (tema.py = sistema de diseño)
tests/                  pruebas automáticas
datos/contawin.db       se crea al primer uso
```

Pruebas: `python -m unittest discover -s tests -v`
