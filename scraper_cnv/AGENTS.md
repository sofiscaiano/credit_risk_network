# AGENTS.md - Guía para Agentes de Código

## Convenciones de Commits

Este proyecto utiliza **Conventional Commits**. Cada cambio debe ser commiteado siguiendo este formato:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Tipos de Commit

- `feat`: Nueva funcionalidad
- `fix`: Corrección de bug
- `docs`: Cambios en documentación
- `style`: Cambios de formato (espacios, tabs, etc.)
- `refactor`: Refactorización de código
- `perf`: Mejoras de performance
- `test`: Cambios en tests
- `chore`: Tareas de mantenimiento
- `ci`: Cambios en CI/CD
- `build`: Cambios en sistema de build

### Scopes Comunes

- `cli`: Interfaz de línea de comandos
- `scraper`: Lógica de scraping
- `pdf`: Descarga de PDFs
- `config`: Configuraciones
- `deps`: Dependencias

### Ejemplos

```bash
feat(scraper): add Playwright integration for PDF downloads

fix(pdf): handle timeout errors in download process

refactor(cli): migrate to typer and rich for better UX

deps: migrate from pip to uv package manager
```

## Proceso de Trabajo

1. **Cada cambio significativo debe ser commiteado**
2. Commits atómicos y descriptivos
3. No acumular cambios no commiteados
4. Usar `git status` frecuentemente

### Política de Commits por Paso

**Regla fundamental**: Cada paso o cambio significativo en la implementación DEBE ser commiteado inmediatamente.

- ✅ Un commit por cada feature, fix o refactor significativo
- ✅ Commitear antes de pasar a la siguiente tarea
- ✅ Mensajes claros siguiendo Conventional Commits
- ❌ No acumular múltiples cambios en un solo commit
- ❌ No dejar el working tree sucio al finalizar una sesión

Ejemplo de flujo:
```bash
# 1. Crear pyproject.toml
git add pyproject.toml
git commit -m "build(deps): migrate from pip to uv package manager"

# 2. Crear CLI
git add src/cnv_scraper/cli.py
git commit -m "feat(cli): add unified CLI with typer and rich"

# 3. Migrar logging
git add src/cnv_scraper/logging_config.py
git commit -m "refactor(logging): migrate to structlog"
```

## Herramientas del Proyecto

- **Gestor de paquetes**: uv (en lugar de pip)
- **CLI Framework**: Typer + Rich
- **Logging**: Structlog
- **Browser Automation**: Playwright
