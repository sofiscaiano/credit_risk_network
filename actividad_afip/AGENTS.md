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

- `cli`: Interfaz de línea de comandos (Typer)
- `afip`: Servicios de consulta a AFIP
- `parser`: Lógica de parseo de respuestas
- `config`: Configuraciones y dotenv
- `deps`: Dependencias

### Ejemplos

```bash
feat(cli): add resumen command with rich tables

fix(afip): handle soap:Server "No existe persona" error gracefully

refactor(parser): centralize A5 response parsing in pydantic models

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
git add src/ratings_afip/cli.py
git commit -m "feat(cli): add typer CLI with resumen, consultar and exportar commands"

# 3. Agregar parser de padrón A5
git add src/ratings_afip/parser.py
git commit -m "feat(parser): add pydantic models and A5 response parser"
```

## Reglas de Ejecución

**NO ejecutar código de forma autónoma sin autorización explícita del usuario.**

- ✅ Escribir el código y preparar el entorno
- ✅ Probar que el script compila (sintaxis)
- ✅ Explicar al usuario cómo ejecutarlo
- ❌ Ejecutar scripts que consuman recursos externos (API, requests, descargas)
- ❌ Ejecutar sin el `go` o autorización explícita del usuario

## Herramientas del Proyecto

- **Gestor de paquetes**: uv (en lugar de pip)
- **CLI Framework**: Typer + Rich
- **Modelado**: Pydantic
- **Conexión AFIP**: afip.py (AFIP SDK)
- **Configuración**: python-dotenv
