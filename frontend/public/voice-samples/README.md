# Voice preview assets

These MP3 files were generated locally with the project's Kokoro 82M engine.
Each catalog voice uses the neutral expression at the native 24 kHz sample
rate, followed by the same loudness-normalized MP3 encoding used by the app.

All voices in a language group read the same sentence for useful comparison:

| Code | Language | Preview sentence |
| --- | --- | --- |
| `a` | American English | Hello, this is a quick preview of my voice. |
| `b` | British English | Hello, this is a short preview of my voice. |
| `e` | Spanish | Hola, esta es una breve muestra de mi voz. |
| `f` | French | Bonjour, voici un court aperçu de ma voix. |
| `h` | Hindi | नमस्ते, यह मेरी आवाज़ का एक छोटा सा नमूना है। |
| `i` | Italian | Ciao, questo è un breve esempio della mia voce. |
| `j` | Japanese | こんにちは、これは私の声の短いサンプルです。 |
| `p` | Brazilian Portuguese | Olá, esta é uma breve amostra da minha voz. |
| `z` | Mandarin Chinese | 你好，这是我的声音简短示例。 |

`backend/tests/test_catalog.py` fully decodes the files and enforces an exact
one-to-one match with the voice catalog. Regeneration should use
`KokoroEngine.synthesize`, `resolve_expression("neutral", None)`, and
`encode_audio(..., OutputFormat.mp3, ..., normalize=True)`.
