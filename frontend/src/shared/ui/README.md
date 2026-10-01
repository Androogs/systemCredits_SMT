# Componentes compartidos

Esta carpeta es la fuente única para UI reutilizable. Las pantallas pueden
componer estos controles con utilidades de Tailwind, pero no deben mantener
copias paralelas de componentes comunes.

- `Boton`: variantes `primario`, `secundario`, `terciario` y `peligro`; tamaños
  `normal` y `compacto`; soporta iconos y estado `cargando`.
- `Alerta`: variantes `informacion`, `exito`, `advertencia` y `error`, con roles
  accesibles por defecto.
- `Tarjeta`: contenedor basado en `div` con atributos HTML estándar.
- `CampoEntrada`: entrada con etiqueta asociada, atributos nativos y error
  accesible.
- `Selector`: selector con etiqueta asociada, opciones y error accesible.

Importación recomendada:

```tsx
import { Alerta, Boton, CampoEntrada, Selector, Tarjeta } from '../shared/ui'
```
