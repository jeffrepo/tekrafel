# -*- coding: utf-8 -*-

import time
import math
import re

from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import requests
import logging
import base64
from lxml import etree
from lxml.builder import ElementMaker
import xml.etree.ElementTree as ET
import datetime
from requests import get
from lxml.etree import CDATA
import xmltodict, json

class AccountMove(models.Model):
    _inherit = "account.move"

    numero_autorizacion_fel = fields.Char('Numero de autorización')
    numero_documento_fel = fields.Char('Numero de documento')
    serie_documento_fel = fields.Char('Serie de documento')
    codigo_qr = fields.Binary('Qr')
    representacion_grafica_fel = fields.Binary('Representacion gráfica')
    # feel_numero_autorizacion = fields.Char('Feel Numero de autorizacion')
    # feel_serie = fields.Char('Feel serie')
    # feel_numero = fields.Char('Feel numero')
    # feel_uuid = fields.Char('UUID')
    # feel_documento_certificado = fields.Char('Documento Feel')
    incoterm_fel = fields.Selection([
            ('EXW', 'En fábrica'),
            ('FCA', 'Libre transportista'),
            ('FAS', 'Libre al costado del buque'),
            ('FOB', 'Libre a bordo'),
            ('CFR', 'Costo y flete'),
            ('CIF','Costo, seguro y flete'),
            ('CPT','Flete pagado hasta'),
            ('CIP','Flete y seguro pagado hasta'),
            ('DDP','Entregado en destino con derechos pagados'),
            ('DAP','Entregada en lugar'),
            ('DAT','Entregada en terminal'),
            ('ZZZ','Otros')
        ],string="Incoterm",default="EXW",
        help="Termino de entrega")
    # acuse_recibo_sat = fields.Char('Acuse Recibo SAT')
    # codigo_sat = fields.Char('Codigo SAT')
    # formato_xml = fields.Binary('XML Anulado')
    # formato_html = fields.Binary('HTML')
    # formato_pdf = fields.Binary('PDF')
    # response_data1 = fields.Binary('Reponse DATA1')
    # back_procesor = fields.Char('BACK PROCESOR')
    tipo_factura = fields.Selection([('venta','Venta'),('compra', 'Compra o Bien'), ('servicio', 'Servicio'),('varios','Varios'), ('combustible', 'Combustible'),('importacion', 'Importación'),('exportacion','Exportación')],
        string="Tipo de factura")


# 4 1 , exportacion
    def fecha_hora_factura(self, fecha):
        fecha_convertida = datetime.datetime.strptime(str(fecha), '%Y-%m-%d').date().strftime('%Y-%m-%d')
        hora = datetime.datetime.strftime(fields.Datetime.context_timestamp(self, datetime.datetime.now()), "%H:%M:%S")
        fecha_hora_emision = str(fecha_convertida)+'T'+str(hora)
        return fecha_hora_emision

    def soap_autenticacion_tekra(self,factura):
        url = "http://apicertificacion.desa.tekra.com.gt:8080/certificacion/wsdl/"

        #XML
        ip = get('https://api.ipify.org').text

        pn_usuario = factura.company_id.usuario_fel
        pn_clave = factura.company_id.pass_fel
        pn_cliente = str(factura.company_id.cliente_fel)
        pn_contrato =  str(factura.company_id.contrato_fel)
        pn_id_origen = str(factura.company_id.origen_fel)
        pn_ip_origen = ip
        logging.warning(pn_ip_origen)
        payload = """
            <Envelope xmlns="http://schemas.xmlsoap.org/soap/envelope/">
                 <Body>
                <CertificacionDocumento
                xmlns="http://apicertificacion.desa.tekra.com.gt:8080/certificacion/wsdl/">
                <Autenticacion>
                    <pn_usuario>{}</pn_usuario>
                    <pn_clave>{}</pn_clave>
                    <pn_cliente>{}</pn_cliente>
                    <pn_contrato>{}</pn_contrato>
                    <pn_id_origen>{}</pn_id_origen>
                    <pn_ip_origen>{}</pn_ip_origen>
                    <pn_firmar_emisor>SI</pn_firmar_emisor >
                </Autenticacion>
                <Documento>
                <![CDATA[]]>
                </Documento>
                </CertificacionDocumento>
                </Body>
                </Envelope>
        """.format(pn_usuario,pn_clave,pn_cliente,pn_contrato,pn_id_origen,pn_ip_origen)
        # headers
        headers = {
            'Content-Type': 'text/xml; charset=utf-8'
        }
        # POST request
        response = requests.post(url, headers=headers, data=payload)

        # prints the response
        logging.warning('SOAP AUTENTICACION')
        logging.warning(response.json)
        logging.warning(response)
        return response

    def xml_factura(self, factura):
        xmls = ''

        logging.warn(factura)
        # Definimos SHEMALOCATION
        lista_impuestos = []
        if factura.invoice_date != True:
            factura.invoice_date = fields.Date.context_today(self)

        attr_qname = etree.QName("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation")
        DTE_NS = "{http://www.sat.gob.gt/dte/fel/0.2.0}"
        # Nuevo SMAP
        NSMAP = {
            "ds": "http://www.w3.org/2000/09/xmldsig#",
            "dte": "http://www.sat.gob.gt/dte/fel/0.2.0",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance"
        }
        moneda = str(factura.currency_id.name)
        logging.warn(moneda)
        fecha = datetime.datetime.strptime(str(factura.invoice_date), '%Y-%m-%d').date().strftime('%Y-%m-%d')
        hora = datetime.datetime.strftime(fields.Datetime.context_timestamp(self, datetime.datetime.now()), "%H:%M:%S")
        fecha_hora_emision = self.fecha_hora_factura(factura.invoice_date)
        tipo = factura.journal_id.tipo_dte_fel
        # if tipo == 'FACT':
        #
        # if tipo == 'NDEB':
        #
        if tipo == 'NCRE':
            factura_original_id = self.env['account.move'].search([('feel_numero_autorizacion','=',factura.feel_numero_autorizacion),('id','!=',factura.id)])
            if factura_original_id and factura.currency_id.id == factura_original_id.currency_id.id:
                tipo == 'NCRE'
                logging.warn('si es nota credito')
            else:
                raise UserError(str('NOTA DE CREDITO DEBE DE SER CON LA MISMA MONEDA QUE LA FACTURA ORIGINAL'))

        datos_generales = {
            "CodigoMoneda": moneda,
            "FechaHoraEmision":fecha_hora_emision,
            "NumeroAcceso":str(factura.id+100000000),
            "Tipo":tipo
            }
        if tipo == 'FACT' and factura.tipo_factura == 'exportacion':
            datos_generales['Exp'] = "SI"



        nit_company = "CF"
        if '-' in factura.company_id.vat:
            nit_company = factura.company_id.vat.replace('-','')
        else:
            nit_company = factura.company_id.vat

        datos_emisor = {
            "AfiliacionIVA":"GEN",
            "CodigoEstablecimiento": str(factura.journal_id.codigo_establecimiento_fel),
            "CorreoEmisor": str(factura.company_id.email) or "",
            "NITEmisor": str(nit_company),
            # "NITEmisor": '103480307',
            "NombreComercial": factura.journal_id.nombre_comercial_fel,
            "NombreEmisor": factura.company_id.name
        }

        nit_partner = "CF"
        if factura.partner_id.vat:
            if '-' in factura.partner_id.vat:
                nit_partner = factura.partner_id.vat.replace('-','')
            else:
                nit_partner = factura.partner_id.vat

        datos_receptor = {
            "CorreoReceptor": factura.partner_id.email or "",
            "IDReceptor": str(nit_partner),
            "NombreReceptor": factura.partner_id.name
        }


        if tipo == 'FACT' and factura.currency_id !=  self.env.user.company_id.currency_id:
            datos_receptor['IDReceptor'] = "CF"

        ip = get('https://api.ipify.org').text

        pn_usuario = factura.company_id.usuario_fel
        pn_clave = factura.company_id.pass_fel
        pn_cliente = str(factura.company_id.cliente_fel)
        pn_contrato =  str(factura.company_id.contrato_fel)
        pn_id_origen = str(factura.company_id.origen_fel)
        pn_ip_origen = ip
        logging.warning(pn_ip_origen)

        # Creamos los TAGS necesarios

        GTDocumento = etree.Element(DTE_NS+"GTDocumento", {attr_qname: 'http://www.sat.gob.gt/dte/fel/0.1.0'}, Version="0.1", nsmap=NSMAP)
        TagSAT = etree.SubElement(GTDocumento,DTE_NS+"SAT",ClaseDocumento="dte")
        TagDTE = etree.SubElement(TagSAT,DTE_NS+"DTE",ID="DatosCertificados")
        TagDatosEmision = etree.SubElement(TagDTE,DTE_NS+"DatosEmision",ID="DatosEmision")
        TagDatosGenerales = etree.SubElement(TagDatosEmision,DTE_NS+"DatosGenerales",datos_generales)
        # Datos de emisor
        TagEmisor = etree.SubElement(TagDatosEmision,DTE_NS+"Emisor",datos_emisor)
        TagDireccionEmisor = etree.SubElement(TagEmisor,DTE_NS+"DireccionEmisor",{})
        TagDireccion = etree.SubElement(TagDireccionEmisor,DTE_NS+"Direccion",{})
        TagDireccion.text = str(factura.journal_id.direccion_sucursal)
        TagCodigoPostal = etree.SubElement(TagDireccionEmisor,DTE_NS+"CodigoPostal",{})
        TagCodigoPostal.text = str(factura.company_id.zip)
        TagMunicipio = etree.SubElement(TagDireccionEmisor,DTE_NS+"Municipio",{})
        TagMunicipio.text = str(factura.company_id.city)
        TagDepartamento = etree.SubElement(TagDireccionEmisor,DTE_NS+"Departamento",{})
        TagDepartamento.text = str(factura.company_id.state_id.name)
        TagPais = etree.SubElement(TagDireccionEmisor,DTE_NS+"Pais",{})
        TagPais.text = "GT"
        # Datos de receptor
        TagReceptor = etree.SubElement(TagDatosEmision,DTE_NS+"Receptor",datos_receptor)
        TagDireccionReceptor = etree.SubElement(TagReceptor,DTE_NS+"DireccionReceptor",{})
        TagReceptorDireccion = etree.SubElement(TagDireccionReceptor,DTE_NS+"Direccion",{})
        TagReceptorDireccion.text = (factura.partner_id.street or "Ciudad")+" "+(factura.partner_id.street2 or "")
        TagReceptorCodigoPostal = etree.SubElement(TagDireccionReceptor,DTE_NS+"CodigoPostal",{})
        TagReceptorCodigoPostal.text = factura.partner_id.zip or '01001'
        TagReceptorMunicipio = etree.SubElement(TagDireccionReceptor,DTE_NS+"Municipio",{})
        TagReceptorMunicipio.text = factura.partner_id.city or 'Guatemala'
        TagReceptorDepartamento = etree.SubElement(TagDireccionReceptor,DTE_NS+"Departamento",{})
        TagReceptorDepartamento.text = factura.partner_id.state_id.name or 'Guatemala'
        TagReceptorPais = etree.SubElement(TagDireccionReceptor,DTE_NS+"Pais",{})
        TagReceptorPais.text = factura.partner_id.country_id.code or "GT"
        # Frases

        data_frase = {
            "xmlns:dte": "http://www.sat.gob.gt/dte/fel/0.2.0"
        }


        NSMAPFRASE = {
            "dte": "http://www.sat.gob.gt/dte/fel/0.2.0"
        }

        if tipo not in  ['NDEB', 'NCRE']:
            TagFrases = etree.SubElement(TagDatosEmision,DTE_NS+"Frases", {},nsmap=NSMAPFRASE)
            for linea_frase in factura.company_id.fel_frase_ids:
                frases_datos = {}
                if tipo == 'FACT' and factura.currency_id !=  self.env.user.company_id.currency_id:
                    if linea_frase.frase:
                        frases_datos = {"CodigoEscenario": linea_frase.codigo,"TipoFrase":linea_frase.frase}
                    else:
                        frases_datos = {"CodigoEscenario": linea_frase.codigo}
                if tipo == 'FACT' and factura.currency_id ==  self.env.user.company_id.currency_id:
                    if int(linea_frase.frase) == 4:
                        continue
                    else:
                        frases_datos = {"CodigoEscenario": linea_frase.codigo,"TipoFrase":linea_frase.frase}
                # if tipo == 'NCRE':
                #     if linea_frase.frase:
                #         frases_datos = {"CodigoEscenario": linea_frase.codigo,"TipoFrase":linea_frase.frase}
                #     else:
                #         frases_datos = {"CodigoEscenario": linea_frase.codigo}
                TagFrase = etree.SubElement(TagFrases,DTE_NS+"Frase",frases_datos)
                # TagFrases.append(TagFrase)


        # Items
        TagItems = etree.SubElement(TagDatosEmision,DTE_NS+"Items",{})

        impuestos_dic = {'IVA': 0}
        tax_iva = False
        # monto_gravable_iva = 0
        # monto_impuesto_iva = 0
        for linea in factura.invoice_line_ids:
            tax_ids = linea.tax_ids
            numero_linea = 1
            bien_servicio = "S" if linea.product_id.type == 'service' else "B"
            linea_datos = {
                "BienOServicio": bien_servicio,
                'NumeroLinea': str(numero_linea)
            }
            numero_linea += 1
            TagItem =  etree.SubElement(TagItems,DTE_NS+"Item",linea_datos)

            cantidad = linea.quantity
            unidad_medida = "UNI"
            descripcion = linea.product_id.name
            if factura.journal_id.descripcion_factura:
                descripcion = linea.name
            if factura.journal_id.producto_descripcion:
                descripcion = str(linea.product_id.name) + ' ' +str(linea.name)
            # precio_unitario = (linea.price_unit * (1 - (linea.discount) / 100.0)) if linea.discount > 0 else linea.price_unit
            precio_unitario = linea.price_unit
            precio = linea.price_unit * linea.quantity
            descuento = ((linea.quantity * linea.price_unit) - linea.price_total) if linea.discount > 0 else 0
            precio_subtotal = linea.price_subtotal
            TagCantidad = etree.SubElement(TagItem,DTE_NS+"Cantidad",{})
            TagCantidad.text = str(cantidad)
            TagUnidadMedida = etree.SubElement(TagItem,DTE_NS+"UnidadMedida",{})
            TagUnidadMedida.text = str(unidad_medida)
            TagDescripcion = etree.SubElement(TagItem,DTE_NS+"Descripcion",{})
            TagDescripcion.text = descripcion
            TagPrecioUnitario = etree.SubElement(TagItem,DTE_NS+"PrecioUnitario",{})
            TagPrecioUnitario.text = '{:.6f}'.format(precio_unitario)
            TagPrecio = etree.SubElement(TagItem,DTE_NS+"Precio",{})
            TagPrecio.text =  '{:.6f}'.format(precio)
            TagDescuento = etree.SubElement(TagItem,DTE_NS+"Descuento",{})
            TagDescuento.text =  str('{:.6f}'.format(descuento))




            logging.warn('IMPUESTOS')
            currency = linea.move_id.currency_id
            logging.warn(precio_unitario)
            taxes = tax_ids.compute_all(precio_unitario-(descuento/linea.quantity), currency, linea.quantity, linea.product_id, linea.move_id.partner_id)

            if len(linea.tax_ids) > 0:
                # impuestos
                TagImpuestos = etree.SubElement(TagItem,DTE_NS+"Impuestos",{})
                for impuesto in taxes['taxes']:
                    logging.warning('PASAS AQIO')
                    nombre_impuesto = impuesto['name']
                    valor_impuesto = impuesto['amount']
                    if impuesto['name'] == 'IVA por Pagar':
                        nombre_impuesto = "IVA"
                        tax_iva = True

                    TagImpuesto = etree.SubElement(TagImpuestos,DTE_NS+"Impuesto",{})
                    TagNombreCorto = etree.SubElement(TagImpuesto,DTE_NS+"NombreCorto",{})
                    TagNombreCorto.text = nombre_impuesto
                    TagCodigoUnidadGravable = etree.SubElement(TagImpuesto,DTE_NS+"CodigoUnidadGravable",{})
                    TagCodigoUnidadGravable.text = "1"
                    TagMontoGravable = etree.SubElement(TagImpuesto,DTE_NS+"MontoGravable",{})
                    TagMontoGravable.text = str(precio_subtotal)
                    TagMontoImpuesto = etree.SubElement(TagImpuesto,DTE_NS+"MontoImpuesto",{})
                    TagMontoImpuesto.text = '{:.6f}'.format(valor_impuesto)
                    # monto_gravable_iva += precio_subtotal
                    # monto_impuesto_iva += valor_impuesto


                    lista_impuestos.append({'nombre': nombre_impuesto, 'monto': valor_impuesto})

            # comentado por el momento
            else:
                TagImpuestos = etree.SubElement(TagItem,DTE_NS+"Impuestos",{})
                TagImpuesto = etree.SubElement(TagImpuestos,DTE_NS+"Impuesto",{})
                TagNombreCorto = etree.SubElement(TagImpuesto,DTE_NS+"NombreCorto",{})
                TagNombreCorto.text = "IVA"
                TagCodigoUnidadGravable = etree.SubElement(TagImpuesto,DTE_NS+"CodigoUnidadGravable",{})
                TagCodigoUnidadGravable.text = "1"
                if factura.amount_tax == 0:
                    TagCodigoUnidadGravable.text = "2"
                TagMontoGravable = etree.SubElement(TagImpuesto,DTE_NS+"MontoGravable",{})
                TagMontoGravable.text = str(precio_subtotal)
                TagMontoImpuesto = etree.SubElement(TagImpuesto,DTE_NS+"MontoImpuesto",{})
                TagMontoImpuesto.text = "0.00"
            # if (tipo in ['FACT','NCRE']) and factura.currency_id !=  self.env.user.company_id.currency_id:
            #
            #     TagImpuesto = etree.SubElement(TagImpuestos,DTE_NS+"Impuesto",{})
            #     TagNombreCorto = etree.SubElement(TagImpuesto,DTE_NS+"NombreCorto",{})
            #     TagNombreCorto.text = "IVA"
            #     TagCodigoUnidadGravable = etree.SubElement(TagImpuesto,DTE_NS+"CodigoUnidadGravable",{})
            #     TagCodigoUnidadGravable.text = "1"
            #     if factura.amount_tax == 0:
            #         TagCodigoUnidadGravable.text = "2"
            #     TagMontoGravable = etree.SubElement(TagImpuesto,DTE_NS+"MontoGravable",{})
            #     TagMontoGravable.text = str(precio_subtotal)
            #     TagMontoImpuesto = etree.SubElement(TagImpuesto,DTE_NS+"MontoImpuesto",{})
            #     TagMontoImpuesto.text = "0.00"


            logging.warn(taxes)
            TagTotal = etree.SubElement(TagItem,DTE_NS+"Total",{})
            TagTotal.text = str(linea.price_total)
            # Agregamos Lineas

            # TagItems.append(TagItem)
        # if tax_iva:


        TagTotales = etree.SubElement(TagDatosEmision,DTE_NS+"Totales",{})
        TagTotalImpuestos = etree.SubElement(TagTotales,DTE_NS+"TotalImpuestos",{})
        # for i in lista_impuestos:
        #     dato_impuesto = {'NombreCorto': i['nombre'],'TotalMontoImpuesto': i['monto']}
        #     TagTotalImpuesto = etree.SubElement(TagTotalImpuestos,DTE_NS+"TotalImpuesto",dato_impuesto)
        #     TagTotalImpuestos.append(TagTotalImpuesto)

        if len(lista_impuestos) > 0:
            total_impuesto = 0
            logging.warn('EL IMPUESTO')
            for i in lista_impuestos:
                logging.warn(i)
                total_impuesto += float(i['monto'])
            dato_impuesto = {'NombreCorto': lista_impuestos[0]['nombre'],'TotalMontoImpuesto': str('{:.2f}'.format(total_impuesto))}
            TagTotalImpuesto = etree.SubElement(TagTotalImpuestos,DTE_NS+"TotalImpuesto",dato_impuesto)
            TagTotalImpuestos.append(TagTotalImpuesto)
        # else:
        #     logging.warn('ENTRA AL ELSE')
        #     dato_impuesto = {'NombreCorto': 'IVA','TotalMontoImpuesto': str('{:.2f}'.format(0.00))}
        #     TagTotalImpuesto = etree.SubElement(TagTotalImpuestos,DTE_NS+"TotalImpuesto",dato_impuesto)
        #     TagTotalImpuestos.append(TagTotalImpuesto)
        TagGranTotal = etree.SubElement(TagTotales,DTE_NS+"GranTotal",{})
        # TagGranTotal.text = str(factura.amount_total)
        TagGranTotal.text = '{:.3f}'.format(factura.currency_id.round(factura.amount_total))

        if tipo == 'FACT' and (factura.currency_id !=  self.env.user.company_id.currency_id and factura.tipo_factura == 'exportacion'):
            logging.warning('es exportacion')
            dato_impuesto = {'NombreCorto': "IVA",'TotalMontoImpuesto': str(0.00)}
            TagTotalImpuesto = etree.SubElement(TagTotalImpuestos,DTE_NS+"TotalImpuesto",dato_impuesto)
            TagComplementos = etree.SubElement(TagDatosEmision,DTE_NS+"Complementos",{})
            datos_complementos = {
                "IDComplemento": "EXPORTACION",
                "NombreComplemento": "EXPORTACION",
                "URIComplemento": "EXPORTACION"
            }
            TagComplemento = etree.SubElement(TagComplementos,DTE_NS+"Complemento",datos_complementos)
            NSMAP = {
                "cex": "http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0"
            }
            cex = "{http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0}"

            TagExportacion = etree.SubElement(TagComplemento,cex+"Exportacion",{},Version="1",nsmap=NSMAP)
            TagNombreConsignatarioODestinatario = etree.SubElement(TagExportacion,cex+"NombreConsignatarioODestinatario",{})
            TagNombreConsignatarioODestinatario.text = str(factura.partner_id.name)
            TagDireccionConsignatarioODestinatario = etree.SubElement(TagExportacion,cex+"DireccionConsignatarioODestinatario",{})
            # TagDireccionConsignatarioODestinatario.text = str(factura.company_id.street or "")+" "+str(factura.company_id.street2 or "")
            TagDireccionConsignatarioODestinatario.text = str(factura.partner_id.street)

            TagCodigoConsignatarioODestinatario = etree.SubElement(TagExportacion,cex+"CodigoConsignatarioODestinatario",{})
            TagCodigoConsignatarioODestinatario.text = str(factura.company_id.zip or "")
            TagNombreComprador = etree.SubElement(TagExportacion,cex+"NombreComprador",{})
            TagNombreComprador.text = str(factura.partner_id.name)
            TagDireccionComprador = etree.SubElement(TagExportacion,cex+"DireccionComprador",{})
            TagDireccionComprador.text = str(factura.partner_id.street)
            TagCodigoComprador = etree.SubElement(TagExportacion,cex+"CodigoComprador",{})
            TagCodigoComprador.text = str(factura.partner_id.codigo_comprador) if factura.partner_id.codigo_comprador else "N/A"
            TagOtraReferencia = etree.SubElement(TagExportacion,cex+"OtraReferencia",{})
            TagOtraReferencia.text = "N/A"
            TagINCOTERM = etree.SubElement(TagExportacion,cex+"INCOTERM",{})
            TagINCOTERM.text = str(factura.incoterm_fel)
            TagNombreExportador = etree.SubElement(TagExportacion,cex+"NombreExportador",{})
            TagNombreExportador.text = str(factura.company_id.name)
            TagCodigoExportador = etree.SubElement(TagExportacion,cex+"CodigoExportador",{})
            TagCodigoExportador.text = factura.company_id.feel_codigo_exportador if factura.company_id.feel_codigo_exportador else "N/A"



        if tipo == 'NCRE':
            factura_original_id = self.env['account.move'].search([('feel_numero_autorizacion','=',factura.feel_numero_autorizacion),('id','!=',factura.id)])
            if factura_original_id and factura.currency_id.id == factura_original_id.currency_id.id:
                logging.warn('si')
                TagComplementos = etree.SubElement(TagDatosEmision,DTE_NS+"Complementos",{})
                cno = "{http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0}"
                NSMAP_REF = {"cno": "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0"}
                datos_complemento = {'IDComplemento': 'Notas', 'NombreComplemento':'Notas','URIComplemento':'text'}
                TagComplemento = etree.SubElement(TagComplementos,DTE_NS+"Complemento",datos_complemento)
                datos_referencias = {
                    'FechaEmisionDocumentoOrigen': str(factura_original_id.invoice_date),
                    'MotivoAjuste': 'Nota de credito factura',
                    'NumeroAutorizacionDocumentoOrigen': str(factura_original_id.feel_numero_autorizacion),
                    'NumeroDocumentoOrigen': str(factura_original_id.feel_numero),
                    'SerieDocumentoOrigen': str(factura_original_id.feel_serie),
                    'Version': '0.0'
                }
                TagReferenciasNota = etree.SubElement(TagComplemento,cno+"ReferenciasNota",datos_referencias,nsmap=NSMAP_REF)


        xmls = etree.tostring(GTDocumento, encoding="UTF-8")
        # logging.warning(xmls)
        xmls = xmls.decode("utf-8").replace("&amp;", "&").encode("utf-8")
        # logging.warning(xmls)
        xmls_base64 = base64.b64encode(xmls)


        return xmls

    def _post(self,soft=True):
        for factura in self:
            logging.warn(factura)
            if factura.journal_id and factura.move_type == 'out_invoice' and factura.journal_id.tipo_dte_fel and factura.journal_id.codigo_establecimiento_fel:
                xmls = self.xml_factura(factura)
                logging.warning('EL XMLS')
                logging.warning(xmls)
                attr_qname = etree.QName("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation")
                ip = get('https://api.ipify.org').text

                pn_usuario = factura.company_id.usuario_fel
                pn_clave = factura.company_id.pass_fel
                pn_cliente = str(factura.company_id.cliente_fel)
                pn_contrato =  str(factura.company_id.contrato_fel)
                pn_id_origen = str(factura.company_id.origen_fel)
                pn_ip_origen = ip
                logging.warning(pn_ip_origen)

                Envelope = etree.Element("Envelope", {'xmlns': 'http://schemas.xmlsoap.org/soap/envelope/'})
                logging.warning('1')
                BodyTag = etree.SubElement(Envelope,'Body')
                logging.warning('1')
                CertificacionDocumentoTag = etree.SubElement(BodyTag,'CertificacionDocumento',{'xmlns': 'http://apicertificacion.desa.tekra.com.gt:8080/certificacion/wsdl/'})
                logging.warning('1')
                AutenticacionTag = etree.SubElement(CertificacionDocumentoTag, 'Autenticacion')
                logging.warning('1')
                PnUsuarioTag = etree.SubElement(AutenticacionTag, 'pn_usuario')
                logging.warning('1')
                PnUsuarioTag.text =pn_usuario
                logging.warning('1')
                PnClavesTag = etree.SubElement(AutenticacionTag, 'pn_clave')
                PnClavesTag.text =pn_clave
                logging.warning('1')
                PnClienteTag = etree.SubElement(AutenticacionTag, 'pn_cliente')
                PnClienteTag.text =pn_cliente
                logging.warning('1')
                PnContratoTag = etree.SubElement(AutenticacionTag, 'pn_contrato')
                PnContratoTag.text =pn_contrato
                logging.warning('1')
                PnOrigenIdTag = etree.SubElement(AutenticacionTag, 'pn_id_origen')
                PnOrigenIdTag.text =pn_id_origen
                logging.warning('1')
                PnOrigenIpTag = etree.SubElement(AutenticacionTag,'pn_ip_origen')
                PnOrigenIpTag.text =pn_ip_origen
                logging.warning('1')
                FirmarEmisorTag = etree.SubElement(AutenticacionTag, 'pn_firmar_emisor')
                FirmarEmisorTag.text = "SI"
                logging.warning('1')
                DocumentoTag = etree.SubElement(CertificacionDocumentoTag,'Documento')
                # DocumentoTag.text = '<![CDATA[{}]]>'.format(xmls)
                DocumentoTag.text = etree.CDATA(xmls)

                xmls2 = etree.tostring(Envelope, encoding="UTF-8")
                xmls2 = xmls2.decode("utf-8").replace("&amp;", "&").encode("utf-8")
                xmls2_base64 = base64.b64encode(xmls)
                logging.warning('XMLS 2')
                logging.warning(xmls2)
                header = {"content-type": "application/json"}

                logging.warn('RE')
                # json_test = {"raw": }}

                #AUTENTICACION TEKRA
                url = "http://apicertificacion.desa.tekra.com.gt:8080/certificacion/servicio.php"


                # headers
                headers = { 'Content-Type': 'application/xml','Connection': 'keep-alive' }
                # POST request
                response2 = requests.post(url, data=xmls2,headers=headers , verify=False)

                # prints the response
                logging.warning('SOAP AUTENTICACION')
                # obj = xmltodict.parse(response2.text)
                # for o in obj:
                #     logging.warning('-------------')
                #     logging.warning(o)
                #     if len(o) > 0:
                #         for a in o:
                # logging.warning(obj)
                # logging.warning(response2.json())
                # tree = etree.parse(response2.text)
                # for a in tree.findall('CertificacionDocumentoResponse'):
                #     logging.warning('aasasa')
                #     logging.warning(a)
                doc1 = response2.text
                namespaces = {
                    'http://schemas.xmlsoap.org/soap/envelope/': None,
                    'http://schemas.xmlsoap.org/soap/envelope/': None,
                    'http://apicertificacion.desa.tekra.com.gt:8080/certificacion/wsdl/': None
                }
                json_text = xmltodict.parse(response2.text,process_namespaces=True,namespaces=namespaces)
                json_dic = json.dumps(json_text)
                logging.warning(json_dic)
                json_loads = json.loads(json_dic)
                logging.warning(json_loads)
                logging.warning(json_loads['Envelope'])
                if "Envelope" in json_loads:
                    if "Body" in json_loads["Envelope"]:
                        if "CertificacionDocumentoResponse" in json_loads["Envelope"]["Body"]:
                            if "ResultadoCertificacion" in json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]:
                                if "error" in json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]["ResultadoCertificacion"]:
                                    # error = json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]["ResultadoCertificacion"]["error"]
                                    resultado_cdr = json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]
                                    resultado_certificacion_string = json.loads(json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]["ResultadoCertificacion"])
                                    logging.warning("**************************")
                                    # certificado_response = json.loads(json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"])
                                    # logging.warning("ñññññññññññññ111")
                                    # logging.warning(json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]["NumeroAutorizacion"])
                                    # if "RepresentacionGrafica" in certificado_response:
                                    #     logging.warning("ñññññññññññññ")
                                    #     logging.warning('si es RepresentacionGrafica')
                                    # logging.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!11")
                                    # logging.warning(json.loads(json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]["ResultadoCertificacion"]))
                                    if resultado_certificacion_string["error"] == 0:
                                        # logging.warning()
                                        if ("RepresentacionGrafica" and "CodigoQR" and "NumeroAutorizacion" and "NumeroDocumento" and "SerieDocumento") in resultado_cdr:
                                            # rpf = base64.b64decode(resultado_cdr["RepresentacionGrafica"])
                                            representacion_grafica_fel = resultado_cdr["RepresentacionGrafica"]
                                            # base64.encodestring(line[6:11].encode("iso-8859-1"))
                                            logging.warning(representacion_grafica_fel)
                                            logging.warning("[[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]")
                                            codigo_qr = resultado_cdr["CodigoQR"]
                                            numero_autorizacion_fel = resultado_cdr["NumeroAutorizacion"]
                                            numero_documento_fel = resultado_cdr["NumeroDocumento"]
                                            serie_documento_fel = resultado_cdr["SerieDocumento"]
                                            factura.representacion_grafica_fel =representacion_grafica_fel
                                            factura.numero_autorizacion_fel = numero_autorizacion_fel
                                            factura.numero_documento_fel = numero_documento_fel
                                            factura.serie_documento_fel = serie_documento_fel
                                            factura.codigo_qr = codigo_qr
                                    else:
                                        raise UserError(str( error_string["error"]  ))

                # tree = etree.parse(response2.text)
                # doc1.findall('Envelope')
                # # lst = stuff.findall('CertificacionDocumentoResponse')
                # logging.warning(stuff)
                    # print "%s: '%s'" % (elt.tag, elt.text)
                # for elem in tree.iter():
                #     logging.warning(elem)
                # root = doc1.getroot()
                # for element in root.findall("SOAP-ENV:Envelope"):
                #     project = element.find("ResultadoCertificacion").text

                # logging.warning(root)
                # logging.warning(response2)


                # logging.warning('TEST')
                # js = {
                #     "Username": str(factura.company_id.usuario_fel),
                #     "Password":str(factura.company_id.pass_fel)
                #     }
                #
                # reponsea_api = requests.post("https://felgttestaws.digifact.com.gt/felapiv2/api/login/get_token",json= js,headers=header,verify=False )
                # if factura.company_id.prueba_fel == False:
                #     reponsea_api = requests.post("https://felgtaws.digifact.com.gt/gt.com.fel.api.v2/api/login/get_token",json= js,headers=header,verify=False )
                #
                # logging.warn('el json request')
                # logging.warn(reponsea_api.json())
                # if 'Token' not in reponsea_api.json():
                #     raise UserError(str( reponsea_api.json()  ))
                # token = reponsea_api.json()['Token']
                # logging.warn('el token')
                # logging.warning(token)
                # header_response =	{
        		# 				"Content-Type": "application/xml",
        		# 				"Authorization": str(token)
        		# 			}
                # url3 = "https://felgttestaws.digifact.com.gt/felapiv2/api/FelRequest?NIT="+str(factura.company_id.nit_digifactfel)+"&TIPO=CERTIFICATE_DTE_XML_TOSIGN&FORMAT=PDF"
                # if factura.company_id.prueba_fel == False:
                #     logging.warn('no es prueba')
                #     url3 = "https://felgtaws.digifact.com.gt/gt.com.fel.api.v2/api/FELRequest?NIT="+str(factura.company_id.nit_digifactfel)+"&TIPO=CERTIFICATE_DTE_XML_TOSIGN&FORMAT=PDF"
                #
                # response = requests.post(url3, data = xmls, headers = header_response,verify=False)
                # # response_text = r.text()
                # response_json=response.json()
                # logging.warn('el response')
                # logging.warn(response_json)
                #
                # if 'Codigo' in response_json:
                #     if response_json['Codigo'] == 1:
                #         factura.acuse_recibo_sat = response_json['AcuseReciboSAT']
                #         factura.codigo_sat = response_json['CodigosSAT']
                #
                #         if response_json['ResponseDATA1']:
                #             factura.formato_xml = response_json['ResponseDATA1']
                #         if response_json['ResponseDATA2']:
                #             factura.formato_html = response_json['ResponseDATA2']
                #         if response_json['ResponseDATA3']:
                #             factura.formato_pdf = response_json['ResponseDATA3']
                #         if response_json['Autorizacion']:
                #             factura.feel_numero_autorizacion = response_json['Autorizacion']
                #         if response_json['Serie']:
                #             factura.feel_serie = response_json['Serie']
                #         if response_json['NUMERO']:
                #             factura.feel_numero = response_json['NUMERO']
                #         if response_json['BACKPROCESOR']:
                #             factura.back_procesor = response_json['BACKPROCESOR']
                #     else:
                #         if ('mensaje' or 'Mensaje') in response_json:
                #             raise UserError(str( response_json['Mensaje']  ))
                #         else:
                #             raise UserError(str( response_json ))
                # else:
                #     raise UserError(str( response_json['Mensaje']  ))

        return super(AccountMove, self)._post(soft)

    def button_draft(self):
        for factura in self:
            if factura.journal_id.tipo_dte_fel and factura.journal_id.codigo_establecimiento_fel:
                attr_qname = etree.QName("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation")
                DTE_NS = "{http://www.sat.gob.gt/dte/fel/0.1.0}"
                # Nuevo SMAP
                NSMAP = {
                    "ds": "http://www.w3.org/2000/09/xmldsig#",
                    "dte": "http://www.sat.gob.gt/dte/fel/0.1.0",
                    "xsi": "http://www.w3.org/2001/XMLSchema-instance"
                }
                tipo = factura.journal_id.tipo_dte_fel
                GTAnulacionDocumento = etree.Element(DTE_NS+"GTAnulacionDocumento", {attr_qname: 'http://www.sat.gob.gt/dte/fel/0.1.0'}, Version="0.1", nsmap=NSMAP)
                datos_sat = {'ClaseDocumento': 'dte'}
                TagSAT = etree.SubElement(GTAnulacionDocumento,DTE_NS+"SAT",{})
                # dato_anulacion = {'ID': 'DatosCertificados'}
                dato_anulacion = {"ID": "DatosCertificados"}
                TagAnulacionDTE = etree.SubElement(TagSAT,DTE_NS+"AnulacionDTE",dato_anulacion)
                fecha_factura = self.fecha_hora_factura(factura.invoice_date)
                fecha_anulacion = datetime.datetime.strftime(fields.Datetime.context_timestamp(self, datetime.datetime.now()), "%Y-%m-%d")
                hora_anulacion = datetime.datetime.strftime(fields.Datetime.context_timestamp(self, datetime.datetime.now()), "%H:%M:%S")
                fecha_anulacion = str(fecha_anulacion)+'T'+str(hora_anulacion)
                nit_partner = "CF"
                if factura.partner_id.vat:
                    if '-' in factura.partner_id.vat:
                        nit_partner = factura.partner_id.vat.replace('-','')
                    else:
                        nit_partner = factura.partner_id.vat


                nit_company = "CF"
                if '-' in factura.company_id.vat:
                    nit_company = factura.company_id.vat.replace('-','')
                else:
                    nit_company = factura.company_id.vat

                datos_generales = {
                    "ID": "DatosAnulacion",
                    "NumeroDocumentoAAnular": str(factura.feel_numero_autorizacion),
                    "NITEmisor": str(nit_company),
                    "IDReceptor": str(nit_partner),
                    "FechaEmisionDocumentoAnular": fecha_factura,
                    "FechaHoraAnulacion": fecha_anulacion,
                    "MotivoAnulacion": "Anulacion factura"
                }
                if tipo == 'FACT' and factura.currency_id !=  self.env.user.company_id.currency_id:
                    datos_generales['IDReceptor'] = "CF"
                TagDatosGenerales = etree.SubElement(TagAnulacionDTE,DTE_NS+"DatosGenerales",datos_generales)
                # TagCertificacion = etree.SubElement(TagAnulacionDTE,DTE_NS+"Certificacion",{})
                # TagNITCertificador = etree.SubElement(TagCertificacion,DTE_NS+"NITCertificador",{})
                # TagNITCertificador.text = "12521337"
                # TagNombreCertificador = etree.SubElement(TagCertificacion,DTE_NS+"NombreCertificador",{})
                # TagNombreCertificador.text = "INFILE, S.A."
                # TagFechaHoraCertificacion = etree.SubElement(TagCertificacion,DTE_NS+"FechaHoraCertificacion",{})
                # TagFechaHoraCertificacion.text = fecha_anulacion


                xmls = etree.tostring(GTAnulacionDocumento, encoding="UTF-8")
                logging.warn('xmls')
                logging.warn(xmls)
                xmls = xmls.decode("utf-8").replace("&amp;", "&").encode("utf-8")
                xmls_base64 = base64.b64encode(xmls)
                logging.warn(xmls_base64)
                logging.warn('BASE 64')
                logging.warn(xmls_base64.decode("utf-8"))

                header = {"content-type": "application/json"}

                logging.warn('RE')
                # json_test = {"raw": }}
                js = {
                    "Username": str(factura.company_id.usuario_fel),
                    "Password":str(factura.company_id.pass_fel)
                    }
                reponsea_api = requests.post("https://felgttestaws.digifact.com.gt/felapiv2/api/login/get_token",json= js,headers=header,verify=False )
                if factura.company_id.prueba_fel == False:
                    reponsea_api = requests.post("https://felgtaws.digifact.com.gt/gt.com.fel.api.v2/api/login/get_token",json= js,headers=header,verify=False )
                token = reponsea_api.json()['Token']

                url = "https://felgttestaws.digifact.com.gt/felapiv2/api/FelRequest?NIT=" + str(factura.company_id.nit_digifactfel)+"&TIPO=ANULAR_FEL_TOSIGN&FORMAT=XML"
                if factura.company_id.prueba_fel == False:
                    url = "https://felgtaws.digifact.com.gt/gt.com.fel.api.v2/api/FELRequest?NIT=" + str(factura.company_id.nit_digifactfel)+"&TIPO=ANULAR_FEL_TOSIGN&FORMAT=XML"
                # nuevo_json = {
                #     'llave': str(factura.journal_id.feel_llave_pre_firma),
                #     'codigo': str(factura.company_id.vat),
                #     'alias': str(factura.journal_id.feel_usuario),
                #     'es_anulacion': 'Y',
                #     'archivo': xmls_base64.decode("utf-8")
                # }

                # nuevo_json = {
                #     "llave": "cb835d9a7f9c57320b0b4f7290a147b3",
                #     "archivo": xmls_base64.decode("utf-8"),
                #     "codigo": "103480307",
                #     "alias": "TRANSAC_DIGI",
                #     "es_anulacion": "S"
                # }
                # logging.warn('NUEVO JSON ARCHIVO')
                # logging.warn(xmls_base64.decode("utf-8"))

                header_response =	{
        						"Content-Type": "application/xml",
        						"Authorization": str(token)
        					}


                url3 = "https://felgttestaws.digifact.com.gt/felapiv2/api/FelRequest?NIT="+str(factura.company_id.nit_digifactfel)+"&TIPO=ANULAR_FEL_TOSIGN&FORMAT=PDF"
                if factura.company_id.prueba_fel == False:
                    url3 = "https://felgtaws.digifact.com.gt/gt.com.fel.api.v2/api/FELRequest?NIT="+str(factura.company_id.nit_digifactfel)+"&TIPO=ANULAR_FEL_TOSIGN&FORMAT=PDF"

                response = requests.post(url3, data = xmls, headers = header_response,verify=False)
                # response_text = r.text()
                logging.warning('ANULAR')
                response_json=response.json()
                logging.warning(response_json)
                # nuevos_headers = {"content-type": "application/json"}
                # response = requests.post(url, json = nuevo_json, headers = nuevos_headers)
                # respone_json=response.json()
                # logging.warn('RESPONSE JSON')
                # logging.warn(respone_json)
                if response_json['Codigo'] == 1:
                    if response_json['AcuseReciboSAT']:
                        factura.acuse_recibo_sat = response_json['AcuseReciboSAT']
                    if response_json['ResponseDATA1']:
                        factura.formato_xml = response_json['ResponseDATA1']
                    if response_json['ResponseDATA2']:
                        factura.formato_html = response_json['ResponseDATA2']
                    if response_json['ResponseDATA3']:
                        factura.formato_pdf = response_json['ResponseDATA3']
                    if response_json['Autorizacion']:
                        factura.feel_numero_autorizacion = response_json['Autorizacion']
                    if response_json['Serie']:
                        factura.feel_serie = response_json['Serie']
                    if response_json['NUMERO']:
                        factura.feel_numero = response_json['NUMERO']
                    if response_json['BACKPROCESOR']:
                        factura.back_procesor = response_json['BACKPROCESOR']
                        # headers = {
                        #     "USUARIO": str(factura.journal_id.feel_usuario),
                        #     "LLAVE": str(factura.journal_id.feel_llave_firma),
                        #     "IDENTIFICADOR": str(factura.journal_id.name),
                        #     "Content-Type": "application/json",
                        # }
                        #
                        # data = {
                        #     "nit_emisor": str(factura.company_id.vat),
                        #     "correo_copia": str(factura.company_id.email),
                        #     "xml_dte": respone_json["archivo"]
                        # }

                    # headers = {
                    #     "USUARIO": 'TRANSAC_DIGI',
                    #     "LLAVE": '2E6CF6C2F2826E3180702FE139F5B42A',
                    #     "IDENTIFICADOR": str(factura.journal_id.name)+'/'+str(factura.id)+'/'+'ANULACION',
                    #     "Content-Type": "application/json",
                    # }
                    # data = {
                    #     "nit_emisor": '103480307',
                    #     "correo_copia": 'sispavgt@gmail.com',
                    #     "xml_dte": respone_json["archivo"]
                    # }
                else:
                    raise UserError(str('ERROR AL ANULAR'))

        return super(AccountMove, self).button_draft()
