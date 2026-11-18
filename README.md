# Web Project Normalizer

Herramienta Python independiente para analizar y aplicar transformaciones explícitas a proyectos web existentes.

## Requisitos

- Python 3.11 o superior.
- Git y acceso al remoto del template para actualizarlo antes de cada `scan`.
- No requiere Node.js para ejecutar el normalizador. El proyecto objetivo puede necesitar Node.js para sus propias tareas de desarrollo.

## Instalación

```bash
git clone <URL-DEL-REPOSITORIO>
cd web-project-normalizer

python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

El MVP utiliza exclusivamente la biblioteca estándar de Python, por lo que `requirements.txt` está vacío intencionalmente.

## Uso

```bash
python main.py scan --target "../MiProyecto"
python main.py scan --target "../MiProyecto" --json
python main.py scan --target "../MiProyecto" --no-pull
python main.py plan --target "../MiProyecto"
python main.py apply --target "../MiProyecto" --dry-run
python main.py apply --target "../MiProyecto"
python main.py validate --target "../MiProyecto"
```

`scan` recorre el proyecto incluyendo subcarpetas (por ejemplo `client/` y `server/`),
detecta cada `package.json` como un paquete independiente y presenta un resumen legible.
Omite carpetas de dependencias y artefactos generados como `node_modules`, `.git`,
`.next`, `dist` y `build`. Antes del análisis clona o actualiza con `git pull --ff-only`
el template de `https://github.com/branller/web-development-template` dentro de
`.template-cache/`. Si la actualización falla, el escaneo se detiene para no evaluar
contra una referencia desactualizada. Usá `--no-pull --template <ruta>` para un clon
local/offline, `--json` para imprimir JSON y `--report ruta.json` para guardar el reporte.

El scan compara automáticamente con el clon actualizado: dependencias y versiones de
`package.json`, carpetas de código, archivos bajo `components/` y tokens CSS. Muestra un
porcentaje por eje y recomienda cada dependencia, ruta, componente o token que falta o
difiere. [alignment.toml](alignment.toml) permite añadir criterios propios; no es necesario
duplicar ahí el stack ni los componentes que ya existen en el template.
El porcentaje general es el promedio simple de los ejes configurados, para que una lista
larga de tokens no pese más que la estructura o el stack.

`scan` y `plan` agrupan las diferencias en tareas concretas. Los cambios grandes de stack,
estructura o componentes se etiquetan `NOTIFICAR`; el cambio de tokens de diseño queda como
`REVISAR`. `apply` ejecuta las reglas declaradas en `normalizer.toml`, puede integrar
tokens CSS del template en una hoja global existente con Tailwind 4 y crear componentes
solo cuando sus imports son compatibles. Cada cambio crea backup y requiere confirmación.
Migraciones de framework, dependencias faltantes y adaptaciones incompatibles se notifican;
nunca reemplaza código propio implícitamente.

También se pueden especificar las rutas:

```bash
python main.py plan \
  --target "../MiProyecto" \
  --template ".\.template-cache\web-development-template" \
  --config "./normalizer.toml"
```

## Configurar reglas

Editá `normalizer.toml`:

```toml
[[files]]
source = "src/app/globals.css"
target = "src/app/globals.css"
mode = "create_only"
```

- `create_only`: no sobrescribe archivos existentes.
- `replace`: reemplaza el archivo; crea backup externo antes.
- `append`: agrega contenido al final con marcadores para no duplicarlo.

Las rutas `source` son relativas a `template/`; las rutas `target` son relativas al proyecto objetivo.

## Backups

Por defecto se guardan fuera del proyecto objetivo en:

- Windows: `%USERPROFILE%\\.web-project-normalizer\\backups`
- Linux/macOS: `~/.web-project-normalizer/backups`

Los archivos nuevos se eliminan durante un rollback si una operación falla. Los archivos preexistentes se restauran desde el backup.

## Límites del MVP

Esta primera versión implementa auditoría, planificación, copia controlada de componentes compatibles, backups y validaciones básicas. **No reescribe JSX/TSX ni migra automáticamente frameworks.**

La validación CSS es heurística y no reemplaza un parser CSS, TypeScript, ESLint ni un build real.

## Alcance y cambios locales

- No instala paquetes en el proyecto objetivo.
- No ejecuta npm/pnpm.
- No modifica el proyecto objetivo ni sus dependencias.
- `scan` sí actualiza el clon aislado de referencia en `.template-cache/`.
- Solo modifica destinos declarados en `normalizer.toml`.
- No sobrescribe por defecto.
- Rechaza rutas que intenten salir de los directorios permitidos.

## Recomendación

Empezá con `scan` y `plan`. Revisá el plan y recién después ejecutá `apply`.
