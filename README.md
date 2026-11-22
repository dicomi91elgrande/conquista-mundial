# Conquista Mundial — overlay para TikTok LIVE

Dinámica de regalos independiente del juego (pensada para la franja superior mientras juegas a GeoGuessr).

## Reglas

- Cada ronda hay un **TOP 3 de donadores**. Al acabar tu ronda pulsas **FIN DE RONDA** en el panel:
  - **TOP 1** → gana el derecho a conquistar un país. Lo pide en el chat con el comando `conquisto` + país
    (`conquistotailandia`, `conquisto tailandia`, `conquisto a Japón`…). Solo cuenta el comando del ganador.
  - **TOP 2** → «Mención de honor» en el overlay durante la ronda siguiente.
- **País libre** → conquistado. Su **valor** es lo que donó el ganador en esa ronda.
- **País propio** → lo refuerza (suma al valor).
- **País de otro** → **batalla** con cuenta atrás (90 s por defecto). El atacante empieza con lo que donó;
  el dueño, con el valor del país. Los regalos de cada uno suman a su lado. Gana el que más tenga
  (empate = defiende el dueño) y esa cifra pasa a ser el nuevo valor. Un regalo en los últimos 10 s da
  prórroga de 10 s (máx. 6 veces). Los regalos de batalla también cuentan para el top de la ronda.
- **Imperios**: ranking por nº de países. **Emperador** de un continente: quien más países tenga en él (mínimo 3).

## Arrancar

```
python server.py
```

- Overlay: `http://localhost:3210/` (diseñado a 1080×400; `?bg=0` = fondo transparente)
- Panel:   `http://localhost:3210/panel`

El estado se guarda en `state.json` y, además, el panel guarda una copia en el navegador que se
restaura sola si el servidor arranca vacío (útil en Render, donde el disco no persiste).

## WebHooks en Interactive / TikFinity (método POST, URL `…/webhook`)

| Disparador | POST Body |
|---|---|
| Cualquier regalo | `{"event":"gift","username":"{username}","nickname":"{nickname}","imgprofile":"{imgprofile}","coins":"{coins}"}` |
| Mensaje de chat | `{"event":"comment","username":"{username}","nickname":"{nickname}","imgprofile":"{imgprofile}","comment":"{comment}"}` |

Los comentarios que no empiezan por `conquist…` se ignoran.

## Token opcional

Con la variable de entorno `HOOK_TOKEN`, `/webhook` y `/api` exigen `?token=…`
(abre el panel como `/panel?token=…`).
