# -*- coding: utf-8 -*-
"""
xml2altimetria.py
Genera el archivo altimetria.svg (perfil altimétrico de la etapa) a partir de
etapaEsquema.xml.

- Lee el archivo XML y genera en memoria el árbol DOM (xml.etree.ElementTree).
- Extrae la distancia y la altitud de los puntos de la etapa con expresiones XPath.
- Escribe el SVG con la clase Svg: encabezamiento, datos (polilínea del perfil,
  escalas, textos verticales y horizontales) y etiquetas de cierre.

Uso:
  python xml2altimetria.py [archivoEntrada.xml] [archivoSalida.svg]
  (por defecto: etapaEsquema.xml -> altimetria.svg)
"""

import sys
import math
import xml.etree.ElementTree as ET


class Svg:
    """Genera un archivo SVG construyendo su árbol de elementos."""

    def __init__(self, ancho, alto, titulo=""):
        # Encabezamiento del archivo SVG
        self.raiz = ET.Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "version": "1.1",
            "width": str(ancho),
            "height": str(alto),
            "viewBox": "0 0 {0} {1}".format(ancho, alto),
        })
        if titulo:
            ET.SubElement(self.raiz, "title").text = titulo

    @staticmethod
    def _num(valor):
        return "{0:.2f}".format(valor).rstrip("0").rstrip(".")

    def add_rect(self, x, y, ancho, alto, relleno, rx=0):
        ET.SubElement(self.raiz, "rect", {
            "x": self._num(x), "y": self._num(y),
            "width": self._num(ancho), "height": self._num(alto),
            "rx": self._num(rx), "fill": relleno})

    def add_line(self, x1, y1, x2, y2, color, grosor=1, discontinua=False):
        atributos = {"x1": self._num(x1), "y1": self._num(y1),
                     "x2": self._num(x2), "y2": self._num(y2),
                     "stroke": color, "stroke-width": self._num(grosor)}
        if discontinua:
            atributos["stroke-dasharray"] = "3,3"
        ET.SubElement(self.raiz, "line", atributos)

    def add_polyline(self, puntos, relleno, borde, grosor=1):
        texto = " ".join("{0},{1}".format(self._num(x), self._num(y)) for x, y in puntos)
        ET.SubElement(self.raiz, "polyline", {
            "points": texto, "fill": relleno,
            "stroke": borde, "stroke-width": self._num(grosor),
            "stroke-linejoin": "round"})

    def add_polygon(self, puntos, relleno):
        texto = " ".join("{0},{1}".format(self._num(x), self._num(y)) for x, y in puntos)
        ET.SubElement(self.raiz, "polygon", {"points": texto, "fill": relleno})

    def add_text(self, texto, x, y, tamano=12, color="#1a1a1a", negrita=False,
                 anclaje="start", rotacion=0):
        atributos = {
            "x": self._num(x), "y": self._num(y),
            "font-family": "Arial Narrow, Arial, Helvetica, sans-serif",
            "font-size": self._num(tamano), "fill": color,
            "text-anchor": anclaje}
        if negrita:
            atributos["font-weight"] = "bold"
        if rotacion:
            atributos["transform"] = "rotate({0} {1} {2})".format(
                rotacion, self._num(x), self._num(y))
        ET.SubElement(self.raiz, "text", atributos).text = texto

    def add_insignia(self, x, y, texto, relleno, color_texto="#ffffff"):
        """Insignia en forma de escudo (S, M, SP, B, categoría de puerto)."""
        ancho, alto = 26, 24
        d = ("M{0},{1} h{2} a4,4 0 0 1 4,4 v{3} l-{4},8 l-{4},-8 v-{3} a4,4 0 0 1 4,-4 z"
             .format(self._num(x - ancho / 2 + 4), self._num(y), ancho - 8,
                     alto - 4, self._num(ancho / 2)))
        ET.SubElement(self.raiz, "path", {"d": d, "fill": relleno})
        self.add_text(texto, x, y + 16, tamano=12 if len(texto) == 1 else 10,
                      color=color_texto, negrita=True, anclaje="middle")

    def escribir(self, archivo):
        """Escribe el archivo con la declaración XML y las etiquetas de cierre."""
        arbol = ET.ElementTree(self.raiz)
        ET.indent(arbol, space="  ")
        arbol.write(archivo, encoding="UTF-8", xml_declaration=True)


class PuntoPerfil:
    """Punto del perfil: distancia a la salida (km) y altitud (m)."""

    def __init__(self, distancia, altitud, tipo="anonimo", nombre="", insignia=""):
        self.distancia = distancia
        self.altitud = altitud
        self.tipo = tipo            # salida, meta, puerto, sprint, anonimo
        self.nombre = nombre
        self.insignia = insignia


class Altimetria:
    """Lee el XML de la etapa y dibuja su perfil altimétrico en SVG."""

    NS = {"u": "http://www.uniovi.es"}

    # Dimensiones del dibujo
    ANCHO, ALTO = 1200, 620
    X0, X1 = 150, 1050          # extremos horizontales del perfil
    Y_BASE = 500                # línea de altitud 0
    ALTO_PERFIL = 230           # píxeles para la altitud máxima de la escala
    Y_INSIGNIAS = 215           # fila de insignias

    # Colores
    ROJO = "#e8412c"
    ROJO_OSCURO = "#a8261a"
    COLORES_INSIGNIA = {
        "salida": ("#3aa0dc", "#ffffff"),
        "meta": ("#d8231f", "#ffffff"),
        "puerto": ("#c86fb4", "#ffffff"),
        "sprintIntermedio": ("#d7e36b", "#333333"),
        "sprintBonificado": ("#8cc63f", "#ffffff"),
    }

    def __init__(self, archivo_xml, archivo_svg):
        self.archivo_xml = archivo_xml
        self.archivo_svg = archivo_svg
        self.raiz = None
        self.puntos = []
        self.longitud_etapa = 0.0
        self.altitud_escala = 0

    # ------------------------------------------------------------------ #
    #  LECTURA DEL XML Y CONSULTAS XPATH                                  #
    # ------------------------------------------------------------------ #
    def leer_xml(self):
        try:
            self.raiz = ET.parse(self.archivo_xml).getroot()
        except IOError:
            print("No se encuentra el archivo", self.archivo_xml)
            sys.exit(1)
        except ET.ParseError as error:
            print("Error procesando el archivo XML:", self.archivo_xml, error)
            sys.exit(1)

    def texto(self, expresion, nodo=None):
        origen = self.raiz if nodo is None else nodo
        elemento = origen.find(expresion, self.NS)
        return elemento.text.strip() if elemento is not None and elemento.text else ""

    def numero(self, expresion, nodo=None):
        valor = self.texto(expresion, nodo)
        return float(valor) if valor else 0.0

    def obtener_puntos(self):
        """Extrae con XPath la distancia y la altitud de todos los puntos."""
        self.longitud_etapa = self.numero("./u:longitudEtapa")

        # Salida y meta
        self.puntos.append(PuntoPerfil(
            0.0, self.numero("./u:lugarSalida/u:altitud"), "salida",
            self.texto("./u:ciudadInicio"), "S"))
        self.puntos.append(PuntoPerfil(
            self.longitud_etapa, self.numero("./u:lugarLlegada/u:altitud"), "meta",
            self.texto("./u:ciudadFinal"), "M"))

        # Puertos de montaña
        for i, puerto in enumerate(self.raiz.findall(".//u:puertos/u:puertoMontaña", self.NS), 1):
            categoria = puerto.get("categoria")
            insignia = "E" if categoria == "Categoría-Especial" else categoria[0]
            self.puntos.append(PuntoPerfil(
                self.numero("u:distancia", puerto), self.numero("u:altitud", puerto),
                "puerto", "Puerto {0} ({1})".format(i, categoria), insignia))

        # Sprints
        for expresion, tipo, nombre, insignia in (
                (".//u:sprints/u:sprintIntermedio", "sprintIntermedio", "Sprint intermedio", "SP"),
                (".//u:sprints/u:sprintBonificado", "sprintBonificado", "Sprint bonificado", "B")):
            for sprint in self.raiz.findall(expresion, self.NS):
                self.puntos.append(PuntoPerfil(
                    self.numero("u:distancia", sprint), self.numero("u:altitud", sprint),
                    tipo, nombre, insignia))

        # Puntos anónimos
        for anonimo in self.raiz.findall("./u:puntosAnonimos/u:puntoAnonimo", self.NS):
            self.puntos.append(PuntoPerfil(
                self.numero("u:distancia", anonimo), self.numero("u:altitud", anonimo)))

        self.puntos.sort(key=lambda p: p.distancia)
        maxima = max(p.altitud for p in self.puntos)
        self.altitud_escala = max(200, int(math.ceil(maxima / 200.0)) * 200)

    # ------------------------------------------------------------------ #
    #  CÁLCULOS                                                           #
    # ------------------------------------------------------------------ #
    def x(self, distancia):
        return self.X0 + distancia * (self.X1 - self.X0) / self.longitud_etapa

    def y(self, altitud):
        return self.Y_BASE - altitud * self.ALTO_PERFIL / self.altitud_escala

    def desnivel_positivo(self):
        return sum(max(0, b.altitud - a.altitud) for a, b in zip(self.puntos, self.puntos[1:]))

    def inicio_subida(self, indice):
        """Índice del punto donde empieza la subida que termina en 'indice'."""
        i = indice
        while i > 0 and self.puntos[i - 1].altitud < self.puntos[i].altitud:
            i -= 1
        return i

    @staticmethod
    def formato_km(valor):
        return ("{0:.1f}".format(valor).rstrip("0").rstrip(".")).replace(".", ",")

    # ------------------------------------------------------------------ #
    #  DIBUJO                                                             #
    # ------------------------------------------------------------------ #
    def dibujar_escala_vertical(self, svg):
        svg.add_line(self.X0, self.Y_BASE, self.X0, self.y(self.altitud_escala), "#999999", 0.8)
        for altitud in range(0, self.altitud_escala + 1, 200):
            y = self.y(altitud)
            svg.add_line(self.X0 - 5, y, self.X0, y, "#999999", 0.8)
            svg.add_line(self.X0, y, self.X1, y, "#dddddd", 0.5, discontinua=True)
            svg.add_text(str(altitud), self.X0 - 8, y + 3, tamano=8, color="#777777", anclaje="end")

    def dibujar_perfil(self, svg):
        # Polilínea cerrada sobre la base para el efecto "suelo" y relleno
        vertices = [(self.x(0), self.Y_BASE)]
        vertices += [(self.x(p.distancia), self.y(p.altitud)) for p in self.puntos]
        vertices += [(self.x(self.longitud_etapa), self.Y_BASE), (self.x(0), self.Y_BASE)]
        svg.add_polyline(vertices, self.ROJO, self.ROJO_OSCURO, 1.2)

        # Subidas a los puertos en rojo oscuro
        for indice, punto in enumerate(self.puntos):
            if punto.tipo == "puerto":
                inicio = self.inicio_subida(indice)
                tramo = self.puntos[inicio:indice + 1]
                poligono = [(self.x(tramo[0].distancia), self.Y_BASE)]
                poligono += [(self.x(p.distancia), self.y(p.altitud)) for p in tramo]
                poligono += [(self.x(tramo[-1].distancia), self.Y_BASE)]
                svg.add_polygon(poligono, self.ROJO_OSCURO)

        svg.add_line(self.X0 - 10, self.Y_BASE, self.X1 + 10, self.Y_BASE, "#1a1a1a", 1.5)

    def dibujar_hitos(self, svg):
        for punto in self.puntos:
            if punto.tipo == "anonimo":
                continue
            x = self.x(punto.distancia)
            relleno, color_texto = self.COLORES_INSIGNIA[
                "puerto" if punto.tipo == "puerto" else punto.tipo]
            svg.add_insignia(x, self.Y_INSIGNIAS, punto.insignia, relleno, color_texto)

            if punto.tipo in ("salida", "meta"):
                svg.add_line(x, self.Y_INSIGNIAS + 34, x, self.Y_BASE, "#1a1a1a", 1)
                # Nombre de la ciudad en vertical a los lados del perfil
                lado = x - 30 if punto.tipo == "salida" else x + 42
                svg.add_text("{0} / {1:.0f} m".format(punto.nombre.upper(), punto.altitud),
                             lado, self.Y_BASE, tamano=17, negrita=True, rotacion=-90)
            else:
                svg.add_line(x, self.Y_INSIGNIAS + 34, x, self.Y_BASE, "#1a1a1a", 0.8)
                svg.add_text("{0} / {1:.0f} m".format(punto.nombre, punto.altitud),
                             x + 4, self.Y_INSIGNIAS - 8, tamano=11, negrita=True, rotacion=-90)

    def dibujar_escala_horizontal(self, svg):
        for punto in self.puntos:
            if punto.tipo == "anonimo":
                continue
            x = self.x(punto.distancia)
            etiqueta = self.formato_km(punto.distancia)
            if punto.tipo == "meta":
                etiqueta += " km"
            svg.add_line(x, self.Y_BASE, x, self.Y_BASE + 6, "#1a1a1a", 1)
            svg.add_text(etiqueta, x, self.Y_BASE + 20, tamano=11, negrita=True, anclaje="middle")

    def dibujar_textos(self, svg):
        svg.add_text("Etapa {0}: {1}".format(self.texto("./u:numeroEtapa"),
                                             self.texto("./u:nombreEtapa")),
                     40, 40, tamano=22, negrita=True)
        svg.add_text("{0} · {1} km · {2}".format(self.raiz.get("tipoEtapa").capitalize(),
                                                 self.formato_km(self.longitud_etapa),
                                                 self.texto("./u:fechaEtapa")),
                     40, 62, tamano=13, color="#555555")
        svg.add_text("Desnivel positivo: {0:,.0f} m".format(self.desnivel_positivo())
                     .replace(",", "."), self.ANCHO / 2, self.Y_BASE + 70,
                     tamano=15, negrita=True, anclaje="middle")

    def generar(self):
        self.leer_xml()
        self.obtener_puntos()
        svg = Svg(self.ANCHO, self.ALTO, "Altimetría: " + self.texto("./u:nombreEtapa"))
        svg.add_rect(0, 0, self.ANCHO, self.ALTO, "#ffffff")
        self.dibujar_escala_vertical(svg)
        self.dibujar_perfil(svg)
        self.dibujar_hitos(svg)
        self.dibujar_escala_horizontal(svg)
        self.dibujar_textos(svg)
        svg.escribir(self.archivo_svg)
        print("Archivo {0} generado con {1} puntos.".format(self.archivo_svg, len(self.puntos)))


class Aplicacion:
    """Punto de entrada del programa."""

    def __init__(self, argumentos):
        self.entrada = argumentos[1] if len(argumentos) > 1 else "etapaEsquema.xml"
        self.salida = argumentos[2] if len(argumentos) > 2 else "altimetria.svg"

    def ejecutar(self):
        Altimetria(self.entrada, self.salida).generar()


if __name__ == "__main__":
    Aplicacion(sys.argv).ejecutar()
