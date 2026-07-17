# Referencia de Modelos de Generación de Imágenes

## Tabla Comparativa de Modelos

| Modelo | outputQuality | input_fidelity | Resoluciones | Uso recomendado |
|--------|--------------|---------------|-------------|----------------|
| `gpt-image-2` | low, medium, high | No aplica (alta fidelidad por defecto) | Flexible (ver restricciones) | **Predeterminado para producción.** Máxima calidad, edición confiable, fotorrealismo, texto en imagen, workflows identity-sensitive |
| `gpt-image-1.5` | low, medium, high | low, high | 1024x1024, 1024x1536, 1536x1024, auto | Workflows ya validados en migración |
| `gpt-image-1` | low, medium, high | low, high | 1024x1024, 1024x1536, 1536x1024, auto | Solo compatibilidad legacy |
| `gpt-image-1-mini` | low, medium, high | low, high | 1024x1024, 1024x1536, 1536x1024, auto | Grandes volúmenes, ideación rápida, assets no críticos |

---

## gpt-image-2: Restricciones de Tamaño

### Reglas (todas deben cumplirse):
- Longitud máxima de borde: < 3840px
- Ambos bordes deben ser múltiplos de **16**
- Ratio entre borde largo y corto: máximo **3:1**
- Píxeles totales: máximo **8,294,400** (≈ 4K)
- Píxeles totales: mínimo **655,360**

### Tamaños populares para gpt-image-2:

| Label | Resolución | Notas |
|-------|-----------|-------|
| HD Portrait | 1024x1536 | Opción portrait estándar |
| HD Landscape | 1536x1024 | Opción landscape estándar |
| Square | 1024x1024 | Buena opción general |
| Slide / Deck | 1536x864 | Formato widescreen para diapositivas |
| Wide Banner | 1920x1080 | Full HD landscape |
| 2K / QHD | 2560x1440 | Límite superior de confiabilidad recomendado |
| 4K / UHD | 3824x2144 | Experimental. Usar 3824 en lugar de 3840 para cumplir regla |

> **Nota**: Si el output supera 2560x1440 (3,686,400 px totales), los resultados pueden ser más variables. Tratar como experimental.

---

## Parámetros Clave de API

### `outputQuality` / `quality`
- **`low`**: Generación rápida, bajo costo. Suficiente para la mayoría de casos. Ideal para prototipos y producción de alto volumen.
- **`medium`**: Balance entre velocidad y fidelidad. Opción predeterminada sólida para producción.
- **`high`**: Máxima fidelidad. Usar para: texto pequeño denso, infografías complejas, retratos cercanos, ediciones identity-sensitive, outputs de alta resolución.

### `input_fidelity` (solo gpt-image-1, 1.5, 1-mini)
- **`low`**: Más libertad creativa en edición.
- **`high`**: Mayor preservación de detalles de la imagen de entrada. Recomendado para: preservación de identidad, compositing, ediciones quirúrgicas.

> Para **gpt-image-2**, el output ya es de alta fidelidad por defecto y no soporta este parámetro.

### `n` (número de variantes)
- Genera múltiples opciones en un solo call.
- Útil para: logos (n=4), exploración de estilos, AB testing de creativos.

### `background`
- **`opaque`**: Fondo opaco. Usar para mockups de producto cuando se necesita transparencia en un paso posterior de post-procesamiento.
- **`transparent`**: Fondo transparente (PNG). Cuando el modelo lo soporte.

---

## Cuándo Usar Cada Modelo

### Elegir `gpt-image-2`
- Por defecto para la mayoría de workflows de producción
- Cuando la calidad del primer intento reduce retrabajos
- Texto en imagen crítico
- Edición de imagen con preservación de identidad
- Fotorrealismo
- Tamaños personalizados más allá de las opciones predeterminadas

### Elegir `gpt-image-2` con `quality=low`
- Alto volumen de generación
- Experimentación y prototipado rápido
- Casos donde la velocidad domina sobre la calidad perfecta

### Mantener `gpt-image-1.5` o `gpt-image-1`
- Solo para compatibilidad hacia atrás
- Durante migración y validación de prompts

### Elegir `gpt-image-1-mini`
- El costo y el throughput son la restricción principal
- Grandes lotes de variantes exploratorias
- Previsualización de assets que no requieren calidad máxima

---

## Ruta de Migración desde gpt-image-1.5 / gpt-image-1

1. Migrar a `gpt-image-2` para assets de cara al cliente, generación fotorrealista, workflows de edición intensiva, creativos sensibles a marca, texto en imagen, y cualquier caso donde mejor calidad en el primer intento reduce revisiones manuales.
2. Mantener prompts similares al inicio, refinar después de comparar calidad, latencia, y tasa de reintentos.
3. Considerar `gpt-image-1-mini` solo cuando el objetivo principal es reducir costos en lotes grandes de imágenes exploratorias o de baja criticidad.
