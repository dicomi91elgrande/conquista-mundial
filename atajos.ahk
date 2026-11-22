; Conquista Mundial - atajos de teclado globales (AutoHotkey v2).
; Funcionan aunque la ventana activa sea el juego. Cada atajo llama a una URL del servidor.
; Para cerrarlos: icono de la "H" verde en la bandeja del sistema -> Exit.
#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent

BASE := "https://conquista-mundial.onrender.com"
TOKEN := ""        ; si pones HOOK_TOKEN en Render, escríbelo aquí

A_IconTip := "Conquista Mundial - atajos"

Do(action, extra := "") {
    global BASE, TOKEN
    url := BASE "/do/" action "?x=1" extra (TOKEN != "" ? "&token=" TOKEN : "")
    try {
        req := ComObject("WinHttp.WinHttpRequest.5.1")
        req.Open("GET", url, true)
        req.Send()
        if !req.WaitForResponse(10)
            throw Error("timeout")
        if InStr(req.ResponseText, '"ok": true')
            return true
        SoundBeep 400, 150          ; el servidor respondió que no (p. ej. nada que deshacer)
    } catch {
        SoundBeep 250, 400          ; sin conexión con el servidor
    }
    return false
}

; modo prueba desde la línea de comandos:  AutoHotkey64.exe atajos.ahk test undo
if A_Args.Length >= 2 && A_Args[1] = "test" {
    FileAppend (Do(A_Args[2]) ? "ok" : "no") "`n", "*"
    ExitApp
}

; Ctrl + Alt + Shift + letra
^!+r:: Do("end_round")                 ; R = fin de Ronda (premia al top 1 y pone el top a cero)
^!+z:: Do("undo")                      ; Z = deshacer la última acción (2 minutos)
^!+v:: Do("reset_round")               ; V = Vaciar el top sin premiar
^!+n:: Do("cancel_right")              ; N = aNular la conquista pendiente más antigua
^!+m:: Do("battle_time", "&s=30")      ; M = Más tiempo de batalla (+30 s)
^!+b:: Do("battle_resolve")            ; B = resolver la Batalla ya
^!+x:: Do("battle_cancel")             ; X = cancelar la batalla
^!+i:: Do("toggle_view")               ; I = mostrar / ocultar el top de Imperios en el overlay
