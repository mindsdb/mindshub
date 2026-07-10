<a name="readme-top"></a>

<div align="center">

# MindsHub Cowork

**El espacio de trabajo unificado donde los agentes de código abierto hacen el trabajo por ti.**

_Delega lo que sea. Vuelve hecho._

[![Release](https://img.shields.io/github/v/release/mindsdb/minds?logo=github&label=release)](https://github.com/mindsdb/minds/releases)
[![Stars](https://img.shields.io/github/stars/mindsdb/minds?logo=github)](https://github.com/mindsdb/minds/stargazers)
[![License: MIT](https://img.shields.io/github/license/mindsdb/minds)](#-licencia)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%20–%203.13-brightgreen.svg)](https://www.python.org/downloads/)

[Sitio web](https://mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[Documentación](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[App web](https://console.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[Precios](https://mindshub.ai/pricing?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[Discord](https://mindshub.ai/discord)

<p align="center">
  <sub>Otros idiomas: <a href="README.md">English</a> · <a href="README.zh.md">中文</a> · <a href="README.pt.md">Português</a> · <a href="README.hi.md">हिन्दी</a></sub>
</p>

</div>

<p align="center">
  <img alt="MindsHub Cowork — el espacio de trabajo unificado" width="100%" src="https://github.com/user-attachments/assets/769e6463-0a9d-45ae-83d1-ef9e234775d3" />
</p>

**MindsHub Cowork** es el espacio de trabajo unificado donde delegas tareas completas —investigación, análisis, informes, operaciones programadas— y recibes resultados terminados y listos para compartir. Conecta tus datos, dirige cada paso al modelo adecuado, ejecuta agentes de código abierto y convierte su resultado en artefactos que puedes publicar. Es de código abierto y funciona en cualquier lugar: tu máquina, tu VPC o la app alojada.

Este repositorio es el **superproyecto de la plataforma**: reúne la app de escritorio/web, el backend del agente y el motor de datos para que puedas construir y ejecutar toda la pila desde el código fuente.

## Primeros pasos

Elige lo que mejor te convenga:

- **Web — nada que instalar.** Abre **[console.mindshub.ai](https://console.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)** e inicia sesión.
- **macOS.** [Descarga la app de escritorio](https://downloads.mindsdb.com/mindshub-cowork/mac/mindshub-cowork-latest.pkg) (`.pkg`).
- **Windows.** [Descarga la app de escritorio](https://downloads.mindsdb.com/mindshub-cowork/windows/mindshub-cowork-latest.exe) (`.exe`).
- **Ejecútalo como código abierto.** [Compílalo desde el código fuente](#compílalo-desde-el-código-fuente) — ver más abajo.

Gratis para empezar. Pro añade todos los modelos de vanguardia y artefactos privados — ver [precios](https://mindshub.ai/pricing?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme).

## Qué puedes hacer

Para cualquier trabajador del conocimiento —creadores, estrategas y operadores—:

- **Automatiza** trabajo repetitivo de varios pasos que implica leer y escribir: informes, monitoreo, flujos de trabajo recurrentes y operaciones programadas.
- **Crea** herramientas y artefactos internos de IA —apps, dashboards, presentaciones, documentos, análisis— sin necesidad de ingeniería, y publícalos en una URL en vivo para compartir con tu equipo.

## Qué incluye

- **Datos conectados.** Un vault seguro conecta sistemas como BigQuery, Postgres, Gmail, Drive, HubSpot, Notion y Linear. Las credenciales quedan delimitadas por conexión —los agentes nunca ven las claves en bruto.
- **Model Router.** Cambia entre modelos de vanguardia (Claude, GPT, Gemini) y modelos abiertos (DeepSeek, Qwen, Kimi) sin configurar una clave para cada proveedor.
- **Agentes abiertos.** Ejecuta harnesses de código abierto intercambiables —Anton (por defecto) y Hermes— seleccionables desde un menú desplegable.
- **Artefactos.** Convierte la salida del agente en documentos, dashboards, apps y código, y publícalo en una URL en vivo.
- **Memoria, habilidades y programación.** Memoria entre sesiones, una biblioteca de habilidades reutilizable y tareas que se ejecutan según un horario.

## Compílalo desde el código fuente

**1. Clona el repositorio**

```bash
git clone --recurse-submodules https://github.com/mindsdb/minds.git
cd minds
```

**2. Instala las dependencias**

```bash
make setup
```

**3. Ejecuta**

| Modo | Comando |
|---|---|
| App de escritorio (Electron) con hot reload | `make dev` o `make watch` |
| App web en el navegador con hot reload | `make dev-web` |
| Build de producción | `make build` |
| Empaquetar para macOS | `make dist-mac` |
| Empaquetar para Windows | `make dist-win` |
| Compilar la `.app` de macOS desde código local sin confirmar | `make pack-local` |
| Borrar todas las instalaciones y datos locales (empezar de cero) | `make flush` |

> **Empezar de cero:** `make flush` elimina el runtime local (la herramienta uv `cowork-server` y los `backend/*/.venv`) y borra el estado de la app en `~/.anton` (claves de proveedores) y `~/.cowork` (base de datos, hermes, proyectos). Úsalo para probar el flujo de instalación desde cero o para recuperarte de una instalación rota. Pide confirmación —pasa `FORCE=1` para omitirla. El siguiente `make setup` o el próximo arranque de la app reinstala todo. ⚠️ Esto elimina tus conversaciones y claves guardadas.

### Trabajar en ramas de funcionalidades (submódulos)

Este repositorio es un superproyecto que fija (pin) cada módulo (`frontend`, `backend/core_api`, `backend/core_agent`, `backend/data-vault`) a un commit. Para trabajar en ramas de los módulos sin ensuciar el `git status` ni pelear por los pins:

**1. Elige tus ramas** en un `dev.env` (ignorado por git, cópialo de la plantilla):

```bash
cp dev.env.example dev.env      # luego define REF=feat/mi-cosa (o por módulo API_REF=…)
```

**2. `make` sigue esa configuración** —un solo ajuste, para ambas formas de ejecutar:

| Comando | Qué hace |
|---|---|
| `make use` | hace checkout de las ramas de `dev.env` en todos los submódulos |
| `make dev` / `make watch` | ejecuta la app Electron con hot reload contra el código local |
| `make dev-web` | ejecuta la SPA web con hot reload contra el código local |
| `make server` + `make app` | (re)instala el servidor de escritorio desde la rama configurada y lo lanza |
| `make server-local` + `make app-local` | instala el servidor de escritorio desde **código local sin confirmar** y lo lanza |
| `make pack-local` | compila la `.app` de macOS desde código local sin confirmar (sin necesidad de push) |
| `make refs` | muestra qué referencias usará la próxima ejecución |
| `make baseline` | restablece los submódulos a los commits fijados |
| `make pin` | registra los commits actuales de los submódulos como los pins del superproyecto (un commit deliberado) |

Los submódulos están configurados con `ignore = all`, así que tu trabajo en ramas nunca aparece como cambios del superproyecto —el `git status` del repositorio padre se mantiene limpio. Los pins solo se mueven con `make pin`. Consulta [`CLAUDE.md`](CLAUDE.md) para el flujo completo.

## Despliega en cualquier lugar

Cowork está diseñado para un despliegue flexible —infraestructura **en la nube, VPC, on-prem, air-gapped e híbrida**— para que mantengas el control total sobre tu infraestructura, modelos, permisos y datos.

## Ayuda y soporte

- **Haz una pregunta** — únete a la [comunidad de Discord](https://mindshub.ai/discord).
- **Reporta un bug** — abre un [issue en GitHub](https://github.com/mindsdb/minds/issues) con los pasos para reproducirlo.
- **Lee la documentación** — guías, configuración y la API en [docs.mindshub.ai](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme).
- **SLAs empresariales o despliegues a medida** — [contacta al equipo](https://mindshub.ai/contact?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme).

## 🤝 Contribuir

Cowork es de código abierto y las contribuciones son bienvenidas —código, integraciones, documentación, reportes de bugs e ideas de funcionalidades. Lee la [documentación](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) para configurarte, explora los [issues abiertos](https://github.com/mindsdb/minds/issues) y saluda en [Discord](https://mindshub.ai/discord).

## 🔒 Seguridad

¿Encontraste una vulnerabilidad de seguridad? Por favor **no** abras un issue público. Repórtala de forma privada a través de nuestra [política de seguridad](https://github.com/mindsdb/minds/security).

## 📚 Recursos

- [Documentación](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [Blog](https://mindshub.ai/blog?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [Guías de marca y kit de prensa](https://mindshub.ai/press-kit?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [Comunidad de Discord](https://mindshub.ai/discord)

## 📄 Licencia

Este repositorio se publica bajo la [Licencia MIT](LICENSE). Los componentes incluidos se rigen por sus propias licencias —consulta el repositorio de cada submódulo para más detalles.

<p align="right">(<a href="#readme-top">volver arriba</a>)</p>
