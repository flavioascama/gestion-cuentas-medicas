"""Errores compartidos entre robots (Seccion 8.4, Fase 15/16)."""

from __future__ import annotations


class ErrorSinResultado(Exception):
    """La plataforma respondio, pero con un resultado definitivo negativo
    (por ejemplo, ACREDITA SALUD no encontro al asegurado). Reintentar no
    cambia la respuesta: el trabajo pasa a SIN_RESULTADO de inmediato, con
    el mensaje para el usuario, y no habilita la contingencia (que es para
    una plataforma que no responde, RF-23)."""


class ErrorSesionNoDisponible(Exception):
    """Un robot que depende de una sesion asistida (Seccion 8.4) no
    encontro ninguna guardada para su plataforma, o la guardada ya no
    autentica de verdad. El dispatcher del trabajador
    (trabajador/principal.py) la distingue de un fallo comun y pasa el
    trabajo a REQUIERE_SESION en vez de reintentarlo con retroceso
    exponencial. Compartida entre AdaptadorAcreditacionWeb (Fase 15) y
    AdaptadorValidadorTedefWeb (Fase 16) -- no es un error propio de
    ninguno de los dos dominios (acreditacion o validacion TEDEF), es
    puramente una senal de orquestacion del trabajador."""
