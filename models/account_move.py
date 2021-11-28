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

    numero_autorizacion_fel = fields.Char('Numero de autorización',copy=False)
    numero_documento_fel = fields.Char('Numero de documento',copy=False)
    serie_documento_fel = fields.Char('Serie de documento',copy=False)
    codigo_qr = fields.Binary('Qr',copy=False)
    moitivo_anulacion = fields.Char('Motivo anulación',copy=False)
    representacion_grafica_fel = fields.Binary('Factura',copy=False)
    representacion_grafica_anulada_fel = fields.Binary('Factura anulada',copy=False)
    fecha_fel = fields.Char('Fecha fel',copy=False)
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

    def xml_factura(self, factura):
        xmls = ''

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
        fecha = datetime.datetime.strptime(str(factura.invoice_date), '%Y-%m-%d').date().strftime('%Y-%m-%d')
        hora = datetime.datetime.strftime(fields.Datetime.context_timestamp(self, datetime.datetime.now()), "%H:%M:%S")
        fecha_hora_emision = self.fecha_hora_factura(factura.invoice_date)
        tipo = factura.journal_id.tipo_dte_fel

        if tipo == 'NCRE' and factura.move_type == "out_refund":
            factura_original_id = self.env['account.move'].search([('numero_autorizacion_fel','=',factura.numero_autorizacion_fel),('id','!=',factura.id)])
            if factura_original_id and factura.currency_id.id == factura_original_id.currency_id.id:
                tipo == 'NCRE'
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
        modulo_bio = self.env['ir.module.module'].search([('name', '=', 'biotecnica')])
        municipio = str(factura.partner_id.company_id.city) if factura.partner_id.company_id.city else "GUATEMALA"
        if not modulo_bio or modulo_bio.state == 'installed':
            municipio = factura.partner_id.municipio_id.name.upper()

        TagMunicipio = etree.SubElement(TagDireccionEmisor,DTE_NS+"Municipio",{})
        TagMunicipio.text = municipio
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

        # Items
        TagItems = etree.SubElement(TagDatosEmision,DTE_NS+"Items",{})

        impuestos_dic = {'IVA': 0}
        tax_iva = False

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

            currency = linea.move_id.currency_id
            taxes = tax_ids.compute_all(precio_unitario-(descuento/linea.quantity), currency, linea.quantity, linea.product_id, linea.move_id.partner_id)

            if len(linea.tax_ids) > 0:
                # impuestos
                TagImpuestos = etree.SubElement(TagItem,DTE_NS+"Impuestos",{})
                for impuesto in taxes['taxes']:
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

            TagTotal = etree.SubElement(TagItem,DTE_NS+"Total",{})
            TagTotal.text = str(linea.price_total)


        TagTotales = etree.SubElement(TagDatosEmision,DTE_NS+"Totales",{})
        TagTotalImpuestos = etree.SubElement(TagTotales,DTE_NS+"TotalImpuestos",{})

        if len(lista_impuestos) > 0:
            total_impuesto = 0
            for i in lista_impuestos:
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
            factura_original_id = self.env['account.move'].search([('id','=',self._context.get('active_id'))])
            if factura_original_id and factura.currency_id.id == factura_original_id.currency_id.id:
                TagComplementos = etree.SubElement(TagDatosEmision,DTE_NS+"Complementos",{})
                cno = "{http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0}"
                NSMAP_REF = {"cno": "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0"}
                datos_complemento = {'IDComplemento': 'Notas', 'NombreComplemento':'Notas','URIComplemento':'text'}
                TagComplemento = etree.SubElement(TagComplementos,DTE_NS+"Complemento",datos_complemento)
                datos_referencias = {
                    'FechaEmisionDocumentoOrigen': str(factura_original_id[0].invoice_date),
                    # 'MotivoAjuste': 'Nota de credito factura',
                    'NumeroAutorizacionDocumentoOrigen': str(factura_original_id.numero_autorizacion_fel),
                    'NumeroDocumentoOrigen': str(factura_original_id.numero_documento_fel),
                    'SerieDocumentoOrigen': str(factura_original_id.serie_documento_fel),
                    'Version': '1'
                }
                TagReferenciasNota = etree.SubElement(TagComplemento,cno+"ReferenciasNota",datos_referencias,nsmap=NSMAP_REF)


        xmls = etree.tostring(GTDocumento, encoding="UTF-8")
        # logging.warning(xmls)
        xmls = xmls.decode("utf-8").replace("&amp;", "&").encode("utf-8")
        # logging.warning(xmls)
        xmls_base64 = base64.b64encode(xmls)


        return {'xmls': xmls, 'fecha_hora_emision': fecha_hora_emision}

    def _post(self,soft=True):
        for factura in self:
            if factura.journal_id and factura.move_type in ['out_invoice','out_refund'] and factura.journal_id.tipo_dte_fel and factura.journal_id.codigo_establecimiento_fel:
                xmls_factura = self.xml_factura(factura)
                attr_qname = etree.QName("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation")
                ip = get('https://api.ipify.org').text

                pn_usuario = factura.company_id.usuario_fel
                pn_clave = factura.company_id.pass_fel
                pn_cliente = str(factura.company_id.cliente_fel)
                pn_contrato =  str(factura.company_id.contrato_fel)
                pn_id_origen = str(factura.company_id.origen_fel)
                pn_ip_origen = ip

                Envelope = etree.Element("Envelope", {'xmlns': 'http://schemas.xmlsoap.org/soap/envelope/'})
                BodyTag = etree.SubElement(Envelope,'Body')
                CertificacionDocumentoTag = etree.SubElement(BodyTag,'CertificacionDocumento',{'xmlns': 'https://apicertificacion.tekra.com.gt/certificacion/wsdl/'})
                if factura.prueba_fel:
                    CertificacionDocumentoTag = etree.SubElement(BodyTag,'CertificacionDocumento',{'xmlns': 'http://apicertificacion.desa.tekra.com.gt:8080/certificacion/wsdl/'})
                AutenticacionTag = etree.SubElement(CertificacionDocumentoTag, 'Autenticacion')
                PnUsuarioTag = etree.SubElement(AutenticacionTag, 'pn_usuario')
                PnUsuarioTag.text =pn_usuario
                PnClavesTag = etree.SubElement(AutenticacionTag, 'pn_clave')
                PnClavesTag.text =pn_clave
                PnClienteTag = etree.SubElement(AutenticacionTag, 'pn_cliente')
                PnClienteTag.text =pn_cliente
                PnContratoTag = etree.SubElement(AutenticacionTag, 'pn_contrato')
                PnContratoTag.text =pn_contrato
                PnOrigenIdTag = etree.SubElement(AutenticacionTag, 'pn_id_origen')
                PnOrigenIdTag.text =pn_id_origen
                PnOrigenIpTag = etree.SubElement(AutenticacionTag,'pn_ip_origen')
                PnOrigenIpTag.text =pn_ip_origen
                FirmarEmisorTag = etree.SubElement(AutenticacionTag, 'pn_firmar_emisor')
                FirmarEmisorTag.text = "SI"
                DocumentoTag = etree.SubElement(CertificacionDocumentoTag,'Documento')
                DocumentoTag.text = etree.CDATA(xmls_factura['xmls'])

                xmls2 = etree.tostring(Envelope, encoding="UTF-8")
                xmls2 = xmls2.decode("utf-8").replace("&amp;", "&").encode("utf-8")
                # xmls2_base64 = base64.b64encode(xmls)
                header = {"content-type": "application/json"}
                # json_test = {"raw": }}

                #AUTENTICACION TEKRA
                url = "https://apicertificacion.tekra.com.gt/servicio.php"
                if factura.company_id.prueba_fel:
                    url = "http://apicertificacion.desa.tekra.com.gt:8080/certificacion/servicio.php"

                # headers
                headers = { 'Content-Type': 'application/xml','Connection': 'keep-alive' }
                # POST request
                response2 = requests.post(url, data=xmls2,headers=headers , verify=False)

                # prints the response
                doc1 = response2.text
                namespaces = {
                    'http://schemas.xmlsoap.org/soap/envelope/': None,
                    'http://schemas.xmlsoap.org/soap/envelope/': None,
                    'http://apicertificacion.desa.tekra.com.gt:8080/certificacion/wsdl/': None
                }
                json_text = xmltodict.parse(response2.text,process_namespaces=True,namespaces=namespaces)
                json_dic = json.dumps(json_text)
                json_loads = json.loads(json_dic)
                if "Envelope" in json_loads:
                    if "Body" in json_loads["Envelope"]:
                        if "CertificacionDocumentoResponse" in json_loads["Envelope"]["Body"]:
                            if "ResultadoCertificacion" in json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]:
                                if "error" in json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]["ResultadoCertificacion"]:
                                    resultado_cdr = json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]
                                    resultado_certificacion_string = json.loads(json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]["ResultadoCertificacion"])
                                    if resultado_certificacion_string["error"] == 0:
                                        if ("RepresentacionGrafica" and "CodigoQR" and "NumeroAutorizacion" and "NumeroDocumento" and "SerieDocumento") in resultado_cdr:
                                            representacion_grafica_fel = resultado_cdr["RepresentacionGrafica"]
                                            codigo_qr = resultado_cdr["CodigoQR"]
                                            numero_autorizacion_fel = resultado_cdr["NumeroAutorizacion"]
                                            numero_documento_fel = resultado_cdr["NumeroDocumento"]
                                            serie_documento_fel = resultado_cdr["SerieDocumento"]
                                            factura.representacion_grafica_fel =representacion_grafica_fel
                                            factura.numero_autorizacion_fel = numero_autorizacion_fel
                                            factura.numero_documento_fel = numero_documento_fel
                                            factura.serie_documento_fel = serie_documento_fel
                                            factura.codigo_qr = codigo_qr
                                            factura.fecha_fel = xmls_factura['fecha_hora_emision']
                                    else:
                                        raise UserError(str( resultado_certificacion_string ))

        return super(AccountMove, self)._post(soft)

    def xml_factura_anulacion(self, factura):
        xmls = False
        if factura.invoice_date != True:
            factura.invoice_date = fields.Date.context_today(self)

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
            "NumeroDocumentoAAnular": str(factura.numero_autorizacion_fel),
            "NITEmisor": str(nit_company),
            "IDReceptor": str(nit_partner),
            "FechaEmisionDocumentoAnular": str(factura.fecha_fel),
            "FechaHoraAnulacion": fecha_anulacion,
            "MotivoAnulacion": str(factura.moitivo_anulacion) if factura.moitivo_anulacion else "Anulacion factura"
        }
        if tipo == 'FACT' and factura.currency_id !=  self.env.user.company_id.currency_id and factura.tipo_factura == "exportacion":
            datos_generales['IDReceptor'] = "CF"
        TagDatosGenerales = etree.SubElement(TagAnulacionDTE,DTE_NS+"DatosGenerales",datos_generales)

        xmls = etree.tostring(GTAnulacionDocumento, encoding="UTF-8")
        xmls = xmls.decode("utf-8").replace("&amp;", "&").encode("utf-8")
        return xmls

    def button_draft(self):
        for factura in self:
            if factura.journal_id.tipo_dte_fel and factura.journal_id.codigo_establecimiento_fel and factura.representacion_grafica_fel and factura.numero_autorizacion_fel and factura.numero_documento_fel and factura.serie_documento_fel:
                xmls = self.xml_factura_anulacion(factura)
                attr_qname = etree.QName("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation")
                ip = get('https://api.ipify.org').text

                pn_usuario = factura.company_id.usuario_fel
                pn_clave = factura.company_id.pass_fel
                pn_cliente = str(factura.company_id.cliente_fel)
                pn_contrato =  str(factura.company_id.contrato_fel)
                pn_id_origen = str(factura.company_id.origen_fel)
                pn_ip_origen = ip

                Envelope = etree.Element("Envelope", {'xmlns': 'http://schemas.xmlsoap.org/soap/envelope/'})
                BodyTag = etree.SubElement(Envelope,'Body')
                CertificacionDocumentoTag = etree.SubElement(BodyTag,'CertificacionDocumento',{'xmlns': 'http://apicertificacion.desa.tekra.com.gt:8080/certificacion/wsdl/'})
                AutenticacionTag = etree.SubElement(CertificacionDocumentoTag, 'Autenticacion')
                PnUsuarioTag = etree.SubElement(AutenticacionTag, 'pn_usuario')
                PnUsuarioTag.text =pn_usuario
                PnClavesTag = etree.SubElement(AutenticacionTag, 'pn_clave')
                PnClavesTag.text =pn_clave
                PnClienteTag = etree.SubElement(AutenticacionTag, 'pn_cliente')
                PnClienteTag.text =pn_cliente
                PnContratoTag = etree.SubElement(AutenticacionTag, 'pn_contrato')
                PnContratoTag.text =pn_contrato
                PnOrigenIdTag = etree.SubElement(AutenticacionTag, 'pn_id_origen')
                PnOrigenIdTag.text =pn_id_origen
                PnOrigenIpTag = etree.SubElement(AutenticacionTag,'pn_ip_origen')
                PnOrigenIpTag.text =pn_ip_origen
                FirmarEmisorTag = etree.SubElement(AutenticacionTag, 'pn_firmar_emisor')
                FirmarEmisorTag.text = "SI"
                DocumentoTag = etree.SubElement(CertificacionDocumentoTag,'Documento')
                DocumentoTag.text = etree.CDATA(xmls)

                xmls2 = etree.tostring(Envelope, encoding="UTF-8")
                xmls2 = xmls2.decode("utf-8").replace("&amp;", "&").encode("utf-8")
                # xmls2_base64 = base64.b64encode(xmls)

                header = {"content-type": "application/json"}
                # json_test = {"raw": }}

                #AUTENTICACION TEKRA
                url = "https://apicertificacion.tekra.com.gt/servicio.php"
                if factura.company_id.prueba_fel:
                    url = "http://apicertificacion.desa.tekra.com.gt:8080/certificacion/servicio.php"

                # headers
                headers = { 'Content-Type': 'application/xml','Connection': 'keep-alive' }
                # POST request
                response2 = requests.post(url, data=xmls2,headers=headers , verify=False)

                # prints the response
                doc1 = response2.text
                namespaces = {
                    'http://schemas.xmlsoap.org/soap/envelope/': None,
                    'http://schemas.xmlsoap.org/soap/envelope/': None,
                    'http://apicertificacion.desa.tekra.com.gt:8080/certificacion/wsdl/': None
                }
                json_text = xmltodict.parse(response2.text,process_namespaces=True,namespaces=namespaces)
                json_dic = json.dumps(json_text)
                json_loads = json.loads(json_dic)

                if "Envelope" in json_loads:
                    if "Body" in json_loads["Envelope"]:
                        if "CertificacionDocumentoResponse" in json_loads["Envelope"]["Body"]:
                            if "ResultadoCertificacion" in json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]:
                                if "error" in json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]["ResultadoCertificacion"]:
                                    resultado_cdr = json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]
                                    resultado_certificacion_string = json.loads(json_loads["Envelope"]["Body"]["CertificacionDocumentoResponse"]["ResultadoCertificacion"])
                                    if resultado_certificacion_string["error"] == 0:
                                        if ("RepresentacionGrafica"  and "NumeroAutorizacion" and "NumeroDocumento" and "SerieDocumento") in resultado_cdr:
                                            representacion_grafica_anulada_fel = resultado_cdr["RepresentacionGrafica"]
                                            factura.representacion_grafica_anulada_fel = representacion_grafica_anulada_fel
                                    else:
                                        raise UserError( resultado_certificacion_string["error"] )

        return super(AccountMove, self).button_draft()
