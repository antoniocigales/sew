# -*- coding: utf-8 -*-
"""
xml2kml.py
Genera el archivo etapa.kml (planimetría de la etapa) a partir de etapaEsquema.xml.

- Lee el archivo XML y construye en memoria el árbol DOM (xml.etree.ElementTree).
- Obtiene toda la información mediante expresiones XPath.
- Escribe el KML con generación de código basada en plantillas:
  prólogo -> estilos -> marcadores y línea del recorrido -> epílogo.

Colores de los marcadores:
  rojo     -> salida y meta
  verde    -> puertos de montaña
  azul     -> sprints (intermedio y bonificado)
  amarillo -> puntos anónimos (máximo 30)

Uso:
  python xml2kml.py [archivoEntrada.xml] [archivoSalida.kml]
  (por defecto: etapaEsquema.xml -> etapa.kml)
"""

import sys
import xml.etree.ElementTree as ET
from string import Template


class Punto:
    """Punto geográfico de la etapa."""

    def __init__(self, nombre, tipo, longitud, latitud, altitud, distancia, descripcion=""):
        self.nombre = nombre
        self.tipo = tipo              # salida, meta, puerto, sprint, anonimo
        self.longitud = longitud
        self.latitud = latitud
        self.altitud = altitud
        self.distancia = distancia    # km desde la salida
        self.descripcion = descripcion

    def coordenadas(self):
        """Coordenadas en el formato KML: longitud,latitud,altitud"""
        return "{0},{1},{2}".format(self.longitud, self.latitud, self.altitud)


class Xml2Kml:
    """Convierte el archivo XML de una etapa en un archivo KML."""

    # Espacio de nombres del XML (prefijo u: en las expresiones XPath)
    NS = {"u": "http://www.uniovi.es"}

    # Máximo de puntos anónimos que se representan
    MAX_ANONIMOS = 30

    # Estilos: id -> (color KML aabbggrr, icono)
    ESTILOS = {
        "salidaMeta": ("ff0000ff", "http://maps.google.com/mapfiles/kml/paddle/red-circle.png"),
        "puerto":     ("ff00ff00", "http://maps.google.com/mapfiles/kml/paddle/grn-circle.png"),
        "sprint":     ("ffff0000", "http://maps.google.com/mapfiles/kml/paddle/blu-circle.png"),
        "anonimo":    ("ff00ffff", "http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png"),
    }

    ESTILO_POR_TIPO = {
        "salida": "salidaMeta",
        "meta": "salidaMeta",
        "puerto": "puerto",
        "sprint": "sprint",
        "anonimo": "anonimo",
    }

    # ------------------------------------------------------------------ #
    #  PLANTILLAS                                                         #
    # ------------------------------------------------------------------ #
    PLANTILLA_PROLOGO = Template(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
        '<Document>\n'
        '  <name>$nombre</name>\n'
        '  <description>$descripcion</description>\n'
    )

    PLANTILLA_ESTILO = Template(
        '  <Style id="$id">\n'
        '    <IconStyle>\n'
        '      <color>$color</color>\n'
        '      <scale>1.1</scale>\n'
        '      <Icon><href>$icono</href></Icon>\n'
        '    </IconStyle>\n'
        '  </Style>\n'
    )

    PLANTILLA_ESTILO_LINEA = Template(
        '  <Style id="linea">\n'
        '    <LineStyle>\n'
        '      <color>$color</color>\n'
        '      <width>$ancho</width>\n'
        '    </LineStyle>\n'
        '  </Style>\n'
    )

    PLANTILLA_CARPETA_INICIO = Template(
        '  <Folder>\n'
        '    <name>$nombre</name>\n'
    )

    PLANTILLA_CARPETA_FIN = '  </Folder>\n'

    PLANTILLA_MARCADOR = Template(
        '    <Placemark>\n'
        '      <name>$nombre</name>\n'
        '      <description>$descripcion</description>\n'
        '      <styleUrl>#$estilo</styleUrl>\n'
        '      <Point>\n'
        '        <altitudeMode>clampToGround</altitudeMode>\n'
        '        <coordinates>$coordenadas</coordinates>\n'
        '      </Point>\n'
        '    </Placemark>\n'
    )

    PLANTILLA_LINEA = Template(
        '  <Placemark>\n'
        '    <name>Recorrido: $nombre</name>\n'
        '    <styleUrl>#linea</styleUrl>\n'
        '    <LineString>\n'
        '      <tessellate>1</tessellate>\n'
        '      <altitudeMode>clampToGround</altitudeMode>\n'
        '      <coordinates>\n'
        '$coordenadas\n'
        '      </coordinates>\n'
        '    </LineString>\n'
        '  </Placemark>\n'
    )

    PLANTILLA_EPILOGO = (
        '</Document>\n'
        '</kml>\n'
    )

    # ------------------------------------------------------------------ #
    def __init__(self, archivo_xml, archivo_kml):
        self.archivo_xml = archivo_xml
        self.archivo_kml = archivo_kml
        self.raiz = None
        self.puntos = []

    # ------------------------------------------------------------------ #
    #  LECTURA DEL XML Y CONSTRUCCIÓN DEL ÁRBOL DOM                       #
    # ------------------------------------------------------------------ #
    def leer_xml(self):
        """Lee el archivo XML y genera en memoria el árbol DOM."""
        try:
            arbol = ET.parse(self.archivo_xml)
        except IOError:
            print("No se encuentra el archivo", self.archivo_xml)
            sys.exit(1)
        except ET.ParseError as error:
            print("Error procesando el archivo XML:", self.archivo_xml, error)
            sys.exit(1)
        self.raiz = arbol.getroot()

    # ------------------------------------------------------------------ #
    #  CONSULTAS XPATH                                                    #
    # ------------------------------------------------------------------ #
    def texto(self, expresion, nodo=None):
        """Devuelve el texto del primer nodo que cumple la expresión XPath."""
        origen = self.raiz if nodo is None else nodo
        elemento = origen.find(expresion, self.NS)
        return elemento.text.strip() if elemento is not None and elemento.text else ""

    def nodos(self, expresion):
        """Devuelve todos los nodos que cumplen la expresión XPath."""
        return self.raiz.findall(expresion, self.NS)

    def leer_punto(self, nodo, nombre, tipo, distancia=None, descripcion=""):
        """Crea un Punto a partir de un nodo con longitud, latitud y altitud."""
        longitud = self.texto("u:longitud", nodo)
        latitud = self.texto("u:latitud", nodo)
        altitud = self.texto("u:altitud", nodo)
        if distancia is None:
            distancia = float(self.texto("u:distancia", nodo) or 0)
        return Punto(nombre, tipo, longitud, latitud, altitud, distancia, descripcion)

    def obtener_puntos(self):
        """Obtiene con XPath todos los puntos de la etapa."""
        ciudad_inicio = self.texto("./u:ciudadInicio")
        ciudad_final = self.texto("./u:ciudadFinal")
        longitud_etapa = float(self.texto("./u:longitudEtapa") or 0)

        # Salida y meta
        salida = self.raiz.find("./u:lugarSalida", self.NS)
        self.puntos.append(self.leer_punto(salida, "Salida: " + ciudad_inicio, "salida",
                                           distancia=0.0, descripcion="Km 0"))
        llegada = self.raiz.find("./u:lugarLlegada", self.NS)
        self.puntos.append(self.leer_punto(llegada, "Meta: " + ciudad_final, "meta",
                                           distancia=longitud_etapa,
                                           descripcion="Km {0}".format(longitud_etapa)))

        # Puertos de montaña
        for i, puerto in enumerate(self.nodos(".//u:puertos/u:puertoMontaña[@categoria]"), 1):
            categoria = puerto.get("categoria")
            p = self.leer_punto(puerto, "Puerto {0} ({1})".format(i, categoria), "puerto")
            p.descripcion = "Km {0} - {1} m".format(p.distancia, p.altitud)
            self.puntos.append(p)

        # Sprints
        for nodo, nombre in ((".//u:sprints/u:sprintIntermedio", "Sprint intermedio"),
                             (".//u:sprints/u:sprintBonificado", "Sprint bonificado")):
            for sprint in self.nodos(nodo):
                p = self.leer_punto(sprint, nombre, "sprint")
                p.descripcion = "Km {0}".format(p.distancia)
                self.puntos.append(p)

        # Puntos anónimos (limitados a MAX_ANONIMOS)
        anonimos = self.nodos("./u:puntosAnonimos/u:puntoAnonimo")[:self.MAX_ANONIMOS]
        for i, anonimo in enumerate(anonimos, 1):
            p = self.leer_punto(anonimo, "Punto {0}".format(i), "anonimo")
            p.descripcion = "Km {0}".format(p.distancia)
            self.puntos.append(p)

        # Orden del recorrido según la distancia a la salida
        self.puntos.sort(key=lambda punto: punto.distancia)

    # ------------------------------------------------------------------ #
    #  ESCRITURA DEL KML                                                  #
    # ------------------------------------------------------------------ #
    def escribir_prologo(self, salida):
        nombre = "Etapa {0}: {1}".format(self.texto("./u:numeroEtapa"),
                                         self.texto("./u:nombreEtapa"))
        descripcion = "Etapa de {0}. {1} km. Fecha: {2}".format(
            self.raiz.get("tipoEtapa"), self.texto("./u:longitudEtapa"),
            self.texto("./u:fechaEtapa"))
        salida.write(self.PLANTILLA_PROLOGO.substitute(nombre=nombre, descripcion=descripcion))

    def escribir_estilos(self, salida):
        for id_estilo, (color, icono) in self.ESTILOS.items():
            salida.write(self.PLANTILLA_ESTILO.substitute(id=id_estilo, color=color, icono=icono))
        salida.write(self.PLANTILLA_ESTILO_LINEA.substitute(color="ff00a5ff", ancho=4))

    def escribir_marcadores(self, salida):
        carpetas = (("Salida y meta", ("salida", "meta")),
                    ("Puertos de montaña", ("puerto",)),
                    ("Sprints", ("sprint",)),
                    ("Puntos anónimos", ("anonimo",)))
        for nombre_carpeta, tipos in carpetas:
            salida.write(self.PLANTILLA_CARPETA_INICIO.substitute(nombre=nombre_carpeta))
            for punto in self.puntos:
                if punto.tipo in tipos:
                    salida.write(self.PLANTILLA_MARCADOR.substitute(
                        nombre=punto.nombre,
                        descripcion=punto.descripcion,
                        estilo=self.ESTILO_POR_TIPO[punto.tipo],
                        coordenadas=punto.coordenadas()))
            salida.write(self.PLANTILLA_CARPETA_FIN)

    def escribir_linea(self, salida):
        coordenadas = "\n".join("        " + p.coordenadas() for p in self.puntos)
        salida.write(self.PLANTILLA_LINEA.substitute(nombre=self.texto("./u:nombreEtapa"),
                                                     coordenadas=coordenadas))

    def escribir_epilogo(self, salida):
        salida.write(self.PLANTILLA_EPILOGO)

    def escribir_kml(self):
        """Escribe el archivo KML: prólogo, coordenadas y epílogo."""
        try:
            with open(self.archivo_kml, "w", encoding="utf-8") as salida:
                self.escribir_prologo(salida)
                self.escribir_estilos(salida)
                self.escribir_linea(salida)
                self.escribir_marcadores(salida)
                self.escribir_epilogo(salida)
        except IOError:
            print("No se puede crear el archivo", self.archivo_kml)
            sys.exit(1)

    # ------------------------------------------------------------------ #
    def convertir(self):
        self.leer_xml()
        self.obtener_puntos()
        self.escribir_kml()
        print("Archivo {0} generado con {1} puntos.".format(self.archivo_kml, len(self.puntos)))


class Aplicacion:
    """Punto de entrada del programa."""

    def __init__(self, argumentos):
        self.entrada = argumentos[1] if len(argumentos) > 1 else "etapaEsquema.xml"
        self.salida = argumentos[2] if len(argumentos) > 2 else "etapa.kml"

    def ejecutar(self):
        Xml2Kml(self.entrada, self.salida).convertir()


if __name__ == "__main__":
    Aplicacion(sys.argv).ejecutar()
