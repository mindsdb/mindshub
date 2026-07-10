<a name="readme-top"></a>

<div align="center">

# MindsHub

**O espaço de trabalho unificado onde modelos de código aberto fazem as coisas por você.**

_Faça a IA realizar trabalho de verdade. Troque de modelo quando quiser — mantenha tudo o que você construiu._

[![Release](https://img.shields.io/github/v/release/mindsdb/minds?logo=github&label=release)](https://github.com/mindsdb/minds/releases)
[![Stars](https://img.shields.io/github/stars/mindsdb/minds?logo=github)](https://github.com/mindsdb/minds/stargazers)
[![License: MIT](https://img.shields.io/github/license/mindsdb/minds)](#-licença)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%20–%203.13-brightgreen.svg)](https://www.python.org/downloads/)

[Site](https://mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[Documentação](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[App web](https://console.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[Preços](https://mindshub.ai/pricing?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[Discord](https://mindshub.ai/discord)

<p align="center">
  <sub>Outros idiomas: <a href="README.md">English</a> · <a href="README.zh.md">中文</a> · <a href="README.es.md">Español</a> · <a href="README.hi.md">हिन्दी</a></sub>
</p>

</div>

<p align="center">
  <img width="640" height="480" alt="cowork" src="https://github.com/user-attachments/assets/048761b8-aa77-4506-9c4d-32e2fdecbb60" />
</p>

O **MindsHub Cowork** é o espaço de trabalho unificado onde você delega projetos inteiros —apps, sites, pesquisa, análise, relatórios, operações agendadas— e recebe resultados finalizados e prontos para compartilhar. Conecte seus dados, direcione o trabalho para qualquer modelo (aberto ou proprietário), execute agentes de código aberto e transforme a saída deles em aplicações web que você pode publicar. É open source e funciona em qualquer lugar —sua máquina, sua VPC, ou o app hospedado.

Este repositório é o **superprojeto da plataforma**: ele reúne o app de desktop/web, o backend do agente e o motor de dados para que você possa compilar e executar toda a stack a partir do código-fonte.

## Comece agora

Escolha o que fizer mais sentido:

- **Web — nada para instalar.** Abra **[console.mindshub.ai](https://console.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)** e faça login.
- **macOS.** [Baixe o app de desktop](https://downloads.mindsdb.com/mindshub-cowork/mac/mindshub-cowork-latest.pkg) (`.pkg`).
- **Windows.** [Baixe o app de desktop](https://downloads.mindsdb.com/mindshub-cowork/windows/mindshub-cowork-latest.exe) (`.exe`).
- **Linux.** [Compile a partir do código-fonte](#compile-a-partir-do-código-fonte).

Grátis para começar. O plano Pro adiciona todos os modelos de ponta e artefatos privados — veja os [preços](https://mindshub.ai/pricing?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme).

## O que você pode fazer

Para todo trabalhador do conhecimento —criadores, estrategistas e operadores:

- **Automatize** trabalho repetitivo e multietapas que envolve leitura e escrita: relatórios, monitoramento, fluxos recorrentes e operações agendadas.
- **Construa** ferramentas e artefatos internos de IA —apps, dashboards, apresentações, documentos, análises— sem precisar de engenharia, e publique em uma URL ativa para compartilhar com sua equipe.

## O que tem por dentro

- **Dados conectados.** Um vault seguro conecta sistemas como BigQuery, Postgres, Gmail, Drive, HubSpot, Notion e Linear. As credenciais ficam restritas por conexão —os agentes nunca veem as chaves brutas.
- **Model Router.** Alterne entre modelos de ponta (Claude, GPT, Gemini) e modelos abertos (DeepSeek, Qwen, Kimi) sem configurar uma chave para cada provedor.
- **Agentes abertos.** Execute harnesses de código aberto intercambiáveis —Anton (padrão) e Hermes— selecionáveis em um menu.
- **Artefatos.** Transforme a saída do agente em documentos, dashboards, apps e código, e publique em uma URL ativa.
- **Memória, habilidades e agendamento.** Memória entre sessões, uma biblioteca de habilidades reutilizável e tarefas que rodam em horários programados.

## Compile a partir do código-fonte

**1. Clone o repositório**

```bash
git clone --recurse-submodules https://github.com/mindsdb/minds.git
cd minds
```

**2. Instale as dependências**

```bash
make setup
```

**3. Execute**

| Modo | Comando |
|---|---|
| App de desktop (Electron) com hot reload | `make dev` ou `make watch` |
| App web no navegador com hot reload | `make dev-web` |
| Build de produção | `make build` |
| Empacotar para macOS | `make dist-mac` |
| Empacotar para Windows | `make dist-win` |
| Compilar o `.app` do macOS a partir do código local não commitado | `make pack-local` |
| Apagar todas as instalações e dados locais (começar do zero) | `make flush` |

> **Começar do zero:** `make flush` remove o runtime local (a ferramenta uv `cowork-server` e os `backend/*/.venv`) e apaga o estado do app em `~/.anton` (chaves de provedores) e `~/.cowork` (banco de dados, hermes, projetos). Use para testar o fluxo de instalação do zero ou recuperar uma instalação corrompida. Pede confirmação —passe `FORCE=1` para pular. O próximo `make setup` ou início do app reinstala tudo. ⚠️ Isso apaga suas conversas e chaves salvas.

### Trabalhando em branches de features (submódulos)

Este repositório é um superprojeto que fixa (pin) cada módulo (`frontend`, `backend/core_api`, `backend/core_agent`, `backend/data-vault`) em um commit. Para trabalhar em branches dos módulos sem poluir o `git status` ou disputar os pins:

**1. Escolha suas branches** em um `dev.env` (ignorado pelo git, copie do modelo):

```bash
cp dev.env.example dev.env      # depois defina REF=feat/minha-coisa (ou por módulo API_REF=…)
```

**2. O `make` segue essa configuração** —um único controle, para os dois modos de execução:

| Comando | O que faz |
|---|---|
| `make use` | faz checkout das branches do `dev.env` em todos os submódulos |
| `make dev` / `make watch` | executa o app Electron com hot reload a partir do código local |
| `make dev-web` | executa a SPA web com hot reload a partir do código local |
| `make server` + `make app` | (re)instala o servidor de desktop a partir da branch configurada e inicia |
| `make server-local` + `make app-local` | instala o servidor de desktop a partir do **código local não commitado** e inicia |
| `make pack-local` | compila o `.app` do macOS a partir do código local não commitado (sem precisar de push) |
| `make refs` | mostra quais referências a próxima execução vai usar |
| `make baseline` | reseta os submódulos para os commits fixados |
| `make pin` | registra os commits atuais dos submódulos como os pins do superprojeto (um commit deliberado) |

Os submódulos são configurados com `ignore = all`, então seu trabalho em branches nunca aparece como alterações do superprojeto —o `git status` do repositório pai permanece limpo. Os pins só mudam via `make pin`. Veja o fluxo completo em [`CLAUDE.md`](CLAUDE.md).

## Implante em qualquer lugar

O Cowork é feito para implantação flexível —infraestrutura em **nuvem, VPC, on-premises, air-gapped e híbrida**— para que você mantenha controle total sobre sua infraestrutura, modelos, permissões e dados.

## Ajuda e suporte

- **Faça uma pergunta** — entre na [comunidade do Discord](https://mindshub.ai/discord).
- **Reporte um bug** — abra uma [issue no GitHub](https://github.com/mindsdb/minds/issues) com os passos para reproduzir.
- **Leia a documentação** — guias, configuração e a API em [docs.mindshub.ai](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme).
- **SLAs empresariais ou implantações personalizadas** — [entre em contato com o time](https://mindshub.ai/contact?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme).

## 🤝 Contribua

O Cowork é open source e contribuições são bem-vindas —código, integrações, documentação, relatos de bugs e ideias de funcionalidades. Leia a [documentação](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) para se preparar, veja as [issues abertas](https://github.com/mindsdb/minds/issues) e dê um alô no [Discord](https://mindshub.ai/discord).

## 🔒 Segurança

Encontrou uma vulnerabilidade de segurança? Por favor, **não** abra uma issue pública. Reporte de forma privada através da nossa [política de segurança](https://github.com/mindsdb/minds/security).

## 📚 Recursos

- [Documentação](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [Blog](https://mindshub.ai/blog?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [Diretrizes de marca e press kit](https://mindshub.ai/press-kit?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [Comunidade do Discord](https://mindshub.ai/discord)

## 📄 Licença

Este repositório é distribuído sob a [Licença MIT](LICENSE). Os componentes empacotados são regidos por suas próprias licenças —consulte o repositório de cada submódulo para mais detalhes.

<p align="right">(<a href="#readme-top">voltar ao topo</a>)</p>
