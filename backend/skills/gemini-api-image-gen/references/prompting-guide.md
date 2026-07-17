# Guía de prompting y casos de uso — Imágenes con Gemini API (Nano Banana)

Principio rector: **describe la escena como narrativa, no como lista de keywords.**
Adapta la plantilla del caso de uso a la intención del usuario y complétala con detalles
específicos (materiales, luz, cámara, propósito, estado de ánimo).

---

## Índice
1. [Generación: Fotorrealismo](#1-fotorrealismo)
2. [Generación: Ilustraciones, stickers e íconos](#2-ilustraciones-stickers-e-íconos)
3. [Generación: Texto preciso en imágenes (logos, portadas, infografías)](#3-texto-preciso-en-imágenes)
4. [Generación: Fotografía de producto / comercial](#4-fotografía-de-producto)
5. [Generación: Diseño minimalista y espacio negativo](#5-diseño-minimalista)
6. [Generación: Arte secuencial (cómic / storyboard)](#6-arte-secuencial)
7. [Generación: Grounding con Google Search](#7-grounding-con-google-search)
8. [Edición: Agregar y quitar elementos](#8-agregar-y-quitar-elementos)
9. [Edición: Inpainting semántico (máscara conversacional)](#9-inpainting-semántico)
10. [Edición: Transferencia de estilo](#10-transferencia-de-estilo)
11. [Edición: Composición multi-imagen](#11-composición-multi-imagen)
12. [Edición: Preservación de detalles de alta fidelidad](#12-preservación-de-detalles)
13. [Edición: De boceto a imagen terminada](#13-de-boceto-a-imagen-terminada)
14. [Consistencia de personaje y vista 360°](#14-consistencia-de-personaje)
15. [Buenas prácticas transversales](#15-buenas-prácticas-transversales)

---

## 1. Fotorrealismo

Usa terminología fotográfica: ángulo de cámara, tipo de lente, iluminación, hora del día, textura.

**Estructura de plantilla:**
```
Una foto [tipo de plano: primer plano / plano medio / gran angular] de [sujeto con detalles
físicos y emocionales], [acción]. El escenario es [lugar y ambiente]. La escena está iluminada
por [tipo de luz: hora dorada / softbox / neón], que destaca [texturas/detalles]. Capturada con
[lente, ej. 85mm de retrato], generando [efecto: bokeh / enfoque nítido]. El estado de ánimo es
[sereno / dramático / enérgico]. Orientación [vertical/horizontal].
```

**Ejemplo probado (de la guía oficial):**
> "Una foto de un retrato en primer plano de un ceramista japonés mayor con arrugas profundas y
> marcadas por el sol, y una sonrisa cálida y sabia. Está inspeccionando cuidadosamente un cuenco
> de té recién esmaltado. El escenario es su taller rústico y soleado. La escena está iluminada
> por la suave luz de la hora dorada que entra por una ventana y destaca la textura fina de la
> arcilla. Capturada con un lente de retrato de 85 mm, con fondo suave y desenfocado (bokeh).
> El estado de ánimo general es sereno y magistral. Orientación vertical."

Truco avanzado: para composiciones isométricas fotorrealistas, pide "una foto capturada que
resultó ser perfectamente isométrica", no una "miniatura".

## 2. Ilustraciones, stickers e íconos

Sé explícito con el estilo y **pide fondo blanco** (el modelo NO genera transparencias).

**Plantilla:**
```
Una calcomanía/ícono de estilo [kawaii / flat / 3D táctil / línea] de [sujeto] con [rasgos].
El diseño presenta [contornos audaces / cel shading / paleta vibrante]. El fondo debe ser blanco.
[Sin texto. / Con el texto "X".]
```

**Ejemplos oficiales:**
> "Una calcomanía de estilo kawaii de un panda rojo feliz con un pequeño sombrero de bambú,
> comiendo una hoja de bambú. Contornos audaces y limpios, cel shading simple, paleta vibrante.
> Fondo blanco."

> "Un ícono que representa un perro lindo. El fondo es blanco. Estilo 3D táctil y colorido.
> No hay texto."

## 3. Texto preciso en imágenes

Gemini destaca renderizando texto. Reglas:
- Especifica el **texto exacto** entre comillas.
- Describe la fuente de forma descriptiva ("sans serif limpia y en negrita", "serif elegante").
- Describe el layout ("llena la vista", "en la esquina junto a un código de barras").
- Para textos largos (artículos, infografías): **genera primero el texto, luego pide la imagen que lo contiene**.
- Usa Gemini 3 Pro Image para producción profesional de recursos con texto.

**Ejemplo — logo:**
> "Crea un logotipo moderno y minimalista para una cafetería llamada 'The Daily Grind'. El texto
> debe estar en una fuente Sans Serif limpia y en negrita. Esquema en blanco y negro. Coloca el
> logotipo en un círculo. Usa un grano de café de forma ingeniosa."

**Ejemplo — portada de revista (composición compleja con texto):**
> "Una foto de la portada brillante de una revista. La portada azul minimalista tiene las palabras
> 'Nano Banana' en letras grandes y negritas, fuente serif que llena la vista. Delante del texto,
> un retrato de una persona con vestido elegante que sostiene el número 2 como punto focal.
> Número de edición y fecha 'Feb 2026' en la esquina con un código de barras. La revista está en
> una estantería contra una pared de yeso naranja, dentro de una tienda de diseño."

**Ejemplo — infografía educativa:**
> "Crea una infografía vibrante que explique la fotosíntesis como si fuera una receta del plato
> favorito de una planta. Muestra los 'ingredientes' (luz solar, agua, CO2) y el 'plato terminado'
> (azúcar/energía). Estilo de página de libro de cocina infantil colorido, apto para 4.º grado."

## 4. Fotografía de producto

Ideal para e-commerce, publicidad y branding.

**Plantilla:**
```
Fotografía de producto en alta resolución con iluminación de estudio de [producto] en
[material/acabado], presentada sobre [superficie]. Iluminación [setup: caja de luz de tres puntos]
para [efecto: luces suaves, sin sombras duras]. Ángulo de cámara: [45 grados elevado / cenital /
nivel de ojo] para mostrar [rasgo clave]. Ultrarrealista, con enfoque nítido en [detalle].
[Relación de aspecto].
```

**Ejemplo oficial:**
> "Fotografía de producto en alta resolución, iluminación de estudio, de una taza de café de
> cerámica minimalista en negro mate sobre hormigón pulido. Caja de luz de tres puntos con luces
> suaves y difusas, sin sombras intensas. Toma ligeramente elevada a 45° para mostrar sus líneas
> limpias. Ultrarrealista, enfoque nítido en el vapor que sale del café. Imagen cuadrada."

Para colocar un logo/marca en un producto, combina con [§12 Preservación de detalles]:
> "Coloca este logotipo en un anuncio de alta gama para un perfume con aroma a banana. El logotipo
> está perfectamente integrado en la botella."

## 5. Diseño minimalista

Fondos para webs, presentaciones o marketing donde se superpondrá texto.

**Ejemplo oficial:**
> "Una composición minimalista con una sola y delicada hoja de arce roja en la parte inferior
> derecha del encuadre. Fondo blanco roto, vasto y vacío, creando espacio negativo significativo
> para texto. Iluminación suave y difusa desde arriba a la izquierda. Imagen cuadrada."

## 6. Arte secuencial

Cómics y storyboards. Requiere consistencia de personaje + descripción de escena. Funciona mejor
con Gemini 3 Pro y 3.1 Flash Image Preview.

**Ejemplo (con imagen de referencia del personaje):**
> "Crea un cómic de 3 paneles con estilo de arte noir y tintas en blanco y negro de alto contraste.
> Coloca al personaje en una escena humorística."

## 7. Grounding con Google Search

Genera imágenes basadas en información en tiempo real: clima, resultados deportivos, mercados,
noticias. Activa la herramienta `google_search` (ver api-reference.md).

**Ejemplos oficiales:**
> "Visualiza el pronóstico del clima de los próximos 5 días en San Francisco como un gráfico
> moderno y limpio. Agrega un visual de qué debería vestir cada día." (ratio 16:9)

> "Crea un gráfico simple pero elegante del partido del Arsenal de anoche en la Champions League."

> "Usa la búsqueda para averiguar cómo se recibió el lanzamiento de X. Escribe un artículo breve
> con encabezados y devuelve una foto del artículo tal como aparecería en una revista brillante."

Con **Búsqueda de imágenes** (solo 3.1 Flash) el modelo usa imágenes web como referencia visual:
> "Usa la búsqueda con imágenes para encontrar imágenes precisas de un quetzal resplandeciente.
> Crea un hermoso fondo de pantalla 3:2 de este pájaro, con degradado natural y composición
> minimalista."

Requisitos legales de despliegue: mostrar atribución con enlace a la página fuente y respetar
navegación directa (1 clic) si se muestran las imágenes fuente. Renderizar `searchEntryPoint`.

## 8. Agregar y quitar elementos

Proporciona la imagen y describe el cambio. El modelo iguala estilo, iluminación y perspectiva.

**Plantilla:** `Con la imagen proporcionada de [sujeto], [agrega/quita/modifica] [elemento].
Haz que [integración: coincida con la iluminación / parezca natural].`

**Ejemplo oficial:**
> "Con la imagen proporcionada de mi gato, agrega un pequeño sombrero de mago tejido en su cabeza.
> Haz que parezca sentado cómodamente y que coincida con la iluminación suave de la foto."

## 9. Inpainting semántico

Define conversacionalmente la "máscara": qué cambiar y **qué mantener intacto**.

**Ejemplo oficial:**
> "Con la imagen proporcionada de una sala de estar, cambia solo el sofá azul por un sofá
> Chesterfield de cuero marrón antiguo. Mantén el resto de la habitación sin cambios, incluidas
> las almohadas del sofá y la iluminación."

## 10. Transferencia de estilo

**Plantilla:** `Transforma la fotografía proporcionada de [contenido] al estilo artístico de
[artista/movimiento]. Conserva la composición original de [elementos], pero renderiza todo con
[características del estilo: pinceladas, paleta].`

**Ejemplo oficial:**
> "Transforma la fotografía de una calle moderna de noche al estilo de 'La noche estrellada' de
> Van Gogh. Conserva la composición de edificios y automóviles, pero renderiza todo con pinceladas
> arremolinadas y empastadas, y una paleta de azules profundos y amarillos brillantes."

También sirve mezclar estilos dentro de una escena:
> "Una foto de una escena cotidiana en una cafetería concurrida. En primer plano, un hombre de
> anime con cabello azul. Una de las personas es un boceto a lápiz y otra es de plastilina."

## 11. Composición multi-imagen

Combina varias imágenes de entrada (hasta 14 en Gemini 3.x) para escenas compuestas: try-on
virtual, mockups, collages, fotos grupales.

**Ejemplo oficial (try-on de moda):**
> "Crea una foto profesional de moda para e-commerce. Toma el vestido floral azul de la primera
> imagen y deja que la mujer de la segunda imagen lo use. Genera una toma realista de cuerpo
> entero, con iluminación y sombras ajustadas a un entorno exterior."

**Ejemplo (foto grupal desde retratos individuales):**
> "Una foto grupal de oficina de estas personas, haciendo caras graciosas." (+ 5 retratos, 5:4, 2K)

Límites de fidelidad: 3.1 Flash = hasta 10 objetos + 4 personajes; 3 Pro = hasta 6 objetos +
5 personajes; 2.5 Flash = mejor con ≤3 imágenes.

## 12. Preservación de detalles

Para conservar rostros, logos o rasgos críticos: **descríbelos con detalle** junto con la edición
y ordena explícitamente que no cambien.

**Ejemplo oficial:**
> "Toma la primera imagen de la mujer con cabello castaño, ojos azules y expresión neutra. Agrega
> el logotipo de la segunda imagen a su camiseta negra. Asegúrate de que el rostro y los rasgos
> permanezcan completamente sin cambios. El logotipo debe verse impreso de forma natural en la
> tela, siguiendo los pliegues de la camisa."

## 13. De boceto a imagen terminada

**Ejemplo oficial:**
> "Convierte este boceto a lápiz de un automóvil futurista en una foto pulida del prototipo
> terminado en una sala de exposición. Conserva las líneas elegantes y el perfil bajo del boceto,
> pero agrega pintura azul metálica y luces de borde de neón."

## 14. Consistencia de personaje

Genera vistas 360° o poses distintas de un personaje pidiendo ángulos de forma **iterativa**,
incluyendo las imágenes previamente generadas como referencia en cada turno. Para poses complejas,
incluye una imagen de referencia de la pose.

**Ejemplo:** (con retrato de entrada) → "Un retrato de estudio de este hombre sobre fondo blanco,
de perfil mirando hacia la derecha." → siguiente turno con ambas imágenes → nuevo ángulo.

## 15. Buenas prácticas transversales

1. **Sé hiperespecífico.** "Armadura de placas élfica ornamentada, grabada con patrones de hojas
   plateadas, cuello alto y hombreras con forma de alas de halcón" > "armadura de fantasía".
2. **Da contexto e intención.** El propósito de la imagen cambia el resultado.
3. **Itera y refina.** Multi-turno con cambios pequeños: "Mantén todo igual, pero haz la
   iluminación un poco más cálida."
4. **Instrucciones paso a paso** para escenas complejas: fondo → elementos medios → primer plano.
5. **Negativos semánticos.** Describe lo deseado en positivo en vez de negar ("una calle vacía y
   desierta" en vez de "sin autos").
6. **Controla la cámara:** wide-angle shot, macro shot, low-angle perspective, 85mm, cenital,
   bokeh, hora dorada, luz de softbox.
7. **Idioma:** para máximo rendimiento usa uno de los idiomas soportados (EN y es-MX incluidos).
8. **Texto largo en imágenes:** primero genera el texto, luego la imagen que lo contiene.
9. **Fondo transparente:** no existe; pide fondo blanco sólido y recorta en postproceso.
