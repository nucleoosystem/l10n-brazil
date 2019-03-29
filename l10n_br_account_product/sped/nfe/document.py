# -*- coding: utf-8 -*-
# Copyright (C) 2013  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html


from __future__ import division, print_function, unicode_literals
import StringIO
from datetime import datetime
import pytz


from odoo.exceptions import Warning as UserError
from odoo.tools.translate import _

from odoo.addons.l10n_br_account.sped.document import FiscalDocument
from odoo.addons.l10n_br_base.tools.misc import punctuation_rm

from ...models.account_invoice_term import (
    FORMA_PAGAMENTO_CARTOES,
    FORMA_PAGAMENTO_SEM_PAGAMENTO,
)


class NFe200(FiscalDocument):
    def __init__(self):
        super(NFe200, self).__init__()
        self.nfe = None
        self.nfref = None
        self.det = None
        self.dup = None

    def _serializer(self, invoices, nfe_environment):

        nfes = []

        for invoice in invoices:

            company = invoice.company_id.partner_id

            self.leiauteNFe = self.get_NFe()

            nfe_nfref = []
            for inv_related in invoice.fiscal_document_related_ids:
                nfe_nfref.append(self._nfe_references(inv_related))

            nfe_ide = self._nfe_identification(
                invoice, company, nfe_environment, nfe_nfref)

            self._in_out_adress(invoice)

            nfe_emit = self._emmiter(invoice, company)
            nfe_dest = self._receiver(invoice, nfe_environment)

            nfe_det = []
            i = 0

            for inv_line in invoice.invoice_line_ids:
                i += 1
                nfe_di = None
                for inv_di in inv_line.import_declaration_ids:
                    nfe_di_adi = []
                    for inv_di_line in inv_di.line_ids:
                        nfe_adi = self._addition(inv_di_line)
                        nfe_di_adi.append(nfe_adi)

                    nfe_di = self._di(inv_di, nfe_di_adi)

                nfe_det.append(self._details(invoice, inv_line, i, nfe_di))

            nfe_cobr = self._encashment_data(invoice)

            nfe_vol = [self._weight_data(invoice)]
            nfe_transp = self._carrier_data(invoice, nfe_vol)

            nfe_retirada = nfe_entrega = None
            if invoice.partner_shipping_id:
                if invoice.partner_id.id != invoice.partner_shipping_id.id:
                    if self.nfe.infNFe.ide.tpNF.valor == 0:
                        nfe_retirada = self.in_out_adress(invoice)
                    else:
                        nfe_entrega = self.in_out_adress(invoice)

            nfe_infadic = self._additional_information(invoice)
            nfe_total = self._total(invoice)
            # TODO
            # self._export(invoice)

            # TODO
            # Gera Chave da NFe
            # self.nfe.gera_nova_chave()
            nfe_autxml = None
            if invoice.company_id.accountant_cnpj_cpf:
                nfe_autxml = self.leiauteNFe.autXMLType(
                    CNPJ=punctuation_rm(
                        invoice.company_id.accountant_cnpj_cpf),
                )

            nfe = self.leiauteNFe.infNFeType(
                versao=invoice.company_id.nfe_version.encode('utf-8'),
                # TODO
                # Id=,
                ide=nfe_ide,
                emit=nfe_emit,
                # TODO - ?
                # avulsa=None,
                dest=nfe_dest,
                retirada=nfe_retirada,
                entrega=nfe_entrega,
                autXML=nfe_autxml,
                det=nfe_det,
                total=nfe_total,
                transp=nfe_transp,
                cobr=nfe_cobr,
                # TODO - ?
                pag=None,
                infAdic=nfe_infadic,
                exporta=None,
                compra=None,
                cana=None,
            )

            output = StringIO.StringIO()
            nfe.export(output, 0)
            nfes.append(output.getvalue())

        return nfes

    def _nfe_identification(
            self, invoice, company, nfe_environment, nfe_nfref):

        # Identificação da NF-e
        #
        if invoice.cfop_ids[0].type == "input":
            tpNF = 0
        else:
            tpNF = 1

        # TODO - Confirmar TAG
        # self.nfe.infNFe.compra.xPed.valor = invoice.name or ''
        xPed = invoice.name or None
        # TODO - get user timezone
        tz = pytz.timezone('America/Sao_Paulo') or pytz.utc

        dhsaient_tz = None
        if invoice.date_in_out:
            dhsaient_tz = str(pytz.utc.localize(datetime.strptime(
                invoice.date_in_out, '%Y-%m-%d %H:%M:%S'))
                .astimezone(tz)).replace(' ', 'T') or ''

        dhemi_tz = None
        if invoice.date_hour_invoice:
            dhemi_tz = str(pytz.utc.localize(datetime.strptime(
                invoice.date_hour_invoice, '%Y-%m-%d %H:%M:%S'))
                .astimezone(tz)).replace(' ', 'T') or ''

        cmunfg = None
        if company.state_id.ibge_code and company.l10n_br_city_id.ibge_code:
            cmunfg = (('%s%s') % (company.state_id.ibge_code,
                                company.l10n_br_city_id.ibge_code))

        ide = self.leiauteNFe.ideType(
            cUF=(company.state_id and
                 company.state_id.ibge_code.encode('utf-8') or ''),
            # cNF='',
            natOp=(invoice.fiscal_category_id.name[:60].encode('utf-8') or ''),
            mod=(invoice.fiscal_document_id.code.encode('utf-8') or ''),
            serie=(invoice.document_serie_id.code.encode('utf-8') or ''),
            nNF=(invoice.fiscal_number.encode('utf-8') or ''),
            dEmi=(invoice.date_invoice.encode('utf-8') or ''),
            dSaiEnt=(str(datetime.strptime(
                invoice.date_in_out,
                '%Y-%m-%d %H:%M:%S').date()).encode('utf-8') or ''),
            cMunFG=cmunfg,
            tpImp=1,  # (1 - Retrato; 2 - Paisagem)
            tpEmis=1,
            tpAmb=nfe_environment.encode('utf-8'),
            finNFe=invoice.nfe_purpose.encode('utf-8'),
            procEmi=0,
            verProc='Odoo Brasil v10.0',
            tpNF=tpNF,
            xPed=xPed,
            idDest=invoice.fiscal_position_id.cfop_id.id_dest.encode('utf-8')
                   or None,
            indFinal=invoice.ind_final.encode('utf-8') or None,
            indPres=invoice.ind_pres.encode('utf-8') or None,
            # TODO - erro de formato do campo
            dhEmi=dhemi_tz.encode('utf-8'),
            dhSaiEnt=dhsaient_tz.encode('utf-8'),
            NFref=nfe_nfref
        )
        return ide

    def _in_out_adress(self, invoice):

        #
        # Endereço de Entrega ou Retirada
        #
        cMun = None
        if (invoice.partner_shipping_id.state_id.ibge_code and
                invoice.partner_shipping_id.l10n_br_city_id.ibge_code):
            cMun = '%s%s' % (
                invoice.partner_shipping_id.
                    state_id.ibge_code.encode('utf-8'),
                invoice.partner_shipping_id.
                    l10n_br_city_id.ibge_code.encode('utf-8'))

        xlgr = None
        if invoice.partner_shipping_id.street:
            xlgr = invoice.partner_shipping_id.street.encode('utf-8')

        nfe_local = self.leiauteNFe.TLocal(
            CNPJ=str(punctuation_rm(invoice.partner_shipping_id.cnpj_cpf)
                     ).encode('utf-8'),
            CPF=None,
            xLgr=xlgr,
            nro=invoice.partner_shipping_id.number or None,
            xCpl=invoice.partner_shipping_id.street2 or None,
            xBairro=invoice.partner_shipping_id.district or 'Sem Bairro',
            cMun=cMun,
            xMun=invoice.partner_shipping_id.
                     l10n_br_city_id.name or None,
            UF=invoice.partner_shipping_id.
                   state_id.code or None,
        )
        return nfe_local

    def _nfe_references(self, inv_related):

        #
        # Documentos referenciadas
        #
        cnpj = cpf = nfe_refnf = refNFe = nfe_refnfp = \
            refCTe = nfe_refecf = None

        if inv_related.cpfcnpj_type == 'cnpj':
            cnpj = punctuation_rm(inv_related.cnpj_cpf)
        else:
            cpf = punctuation_rm(inv_related.cnpj_cpf)

        if inv_related.document_type == 'nf':
            nfe_refnf = self.leiauteNFe.refNFType(
                cUF=(inv_related.state_id and
                     inv_related.state_id.ibge_code or '',),
                AAMM=datetime.strptime(
                    inv_related.date, '%Y-%m-%d').strftime('%y%m') or None,
                CNPJ=cnpj,
                CPF=cpf,
                mod=(inv_related.fiscal_document_id and
                     inv_related.fiscal_document_id.code or ''),
                serie=inv_related.serie or None,
                nNF=inv_related.internal_number or None,
            )

        elif inv_related.document_type == 'nfrural':
            nfe_refnfp = self.leiauteNFe.refNFPType(
                cUF=(inv_related.state_id and
                     inv_related.state_id.ibge_code or '',),
                AAMM=datetime.strptime(
                    inv_related.date, '%Y-%m-%d').strftime('%y%m') or None,
                CNPJ=cnpj,
                CPF=cpf,
                mod=(inv_related.fiscal_document_id and
                     inv_related.fiscal_document_id.code or ''),
                serie=inv_related.serie or None,
                nNF=inv_related.internal_number or None,
            )

        elif inv_related.document_type == 'nfe':
            refNFe = inv_related.access_key or None

        elif inv_related.document_type == 'cte':
            refCTe = inv_related.access_key or None

        elif inv_related.document_type == 'cf':
            nfe_refecf = self.leiauteNFe.refECFType(
                mod=(inv_related.fiscal_document_id and
                     inv_related.fiscal_document_id.code or ''),
                nECF=inv_related.fiscal_number,
                nCOO=inv_related.serie,
            )

        nfe_nfref = self.leiauteNFe.NFrefType(
            refNFe=refNFe,
            refNF=nfe_refnf,
            refNFP=nfe_refnfp,
            refCTe=refCTe,
            refECF=nfe_refecf,
        )

        return nfe_nfref

    def _emmiter(self, invoice, company):
        """Emitente"""

        cmun = None
        if company.state_id.ibge_code and company.l10n_br_city_id.ibge_code:
            cmun = (('%s%s') % (company.state_id.ibge_code,
                                company.l10n_br_city_id.ibge_code))
        if company.district:
            xbairro = company.district.encode('utf-8')
        else:
            xbairro = 'Sem Bairro'

        nfe_enderemit = self.leiauteNFe.TEnderEmi(
            xLgr=company.street,
            nro=company.number,
            xCpl=company.street2 or None,
            xBairro=xbairro,
            cMun=cmun,
            xMun=company.l10n_br_city_id.name,
            UF=company.state_id.code,
            CEP=punctuation_rm(company.zip),
            cPais=company.country_id.bc_code[1:],
            xPais='Brasil',
            fone=punctuation_rm(str(company.phone).replace(' ', '')) or None,
        )

        ie_st = cnae = None
        for inscr_est_line in\
                invoice.company_id.partner_id.other_inscr_est_lines:
            if inscr_est_line.state_id.id == invoice.partner_id.state_id.id:
                ie_st = punctuation_rm(inscr_est_line.inscr_est),

        if invoice.company_id.partner_id.inscr_mun:
            cnae = punctuation_rm(
                    invoice.company_id.cnae_main_id.code)

        nfe_emit = self.leiauteNFe.emitType(
            CNPJ=punctuation_rm(invoice.company_id.partner_id.cnpj_cpf),
            xNome=invoice.company_id.partner_id.legal_name[:60],
            xFant=invoice.company_id.partner_id.name,
            enderEmit=nfe_enderemit,
            IE=punctuation_rm(invoice.company_id.partner_id.inscr_est),
            IEST=ie_st,
            IM=punctuation_rm(
                invoice.company_id.partner_id.inscr_mun) or None,
            CNAE=cnae,
            CRT=invoice.company_id.fiscal_type,
        )

        return nfe_emit

    def _receiver(self, invoice, nfe_environment):
        """Destinatário"""

        partner_bc_code = ''
        partner_cep = ''

        if invoice.partner_id.country_id.bc_code:
            partner_bc_code = invoice.partner_id.country_id.bc_code[1:]

        if invoice.partner_id.country_id.id != \
                invoice.company_id.country_id.id:
            address_invoice_state_code = 'EX'
            address_invoice_city = 'Exterior'
            address_invoice_city_code = '9999999'
        else:
            address_invoice_state_code = invoice.partner_id.state_id.code
            address_invoice_city = invoice.partner_id.l10n_br_city_id.name
            address_invoice_city_code = None
            if invoice.partner_id.state_id.ibge_code and \
                    invoice.partner_id.l10n_br_city_id.ibge_code:
                address_invoice_city_code = (
                        ('%s%s') % (
                    invoice.partner_id.state_id.ibge_code,
                    invoice.partner_id.l10n_br_city_id.ibge_code))
            partner_cep = punctuation_rm(invoice.partner_id.zip)

        nfe_ender_dest = self.leiauteNFe.TEndereco(
            xLgr=invoice.partner_id.street or None,
            nro=invoice.partner_id.number,
            xCpl=invoice.partner_id.street2 or None,
            xBairro=invoice.partner_id.district or 'Sem Bairro',
            cMun=address_invoice_city_code,
            xMun=address_invoice_city,
            UF=address_invoice_state_code,
            CEP=partner_cep,
            cPais=partner_bc_code,
            xPais=invoice.partner_id.country_id.name,
            fone=punctuation_rm(
                invoice.partner_id.phone).replace(' ', ''),
        )

        cnpj = cpf = ie = None
        # Se o ambiente for de teste deve ser
        # escrito na razão do destinatário
        if nfe_environment == 2 or nfe_environment == '2':
            xnome = 'NF-E EMITIDA EM AMBIENTE DE' \
                    ' HOMOLOGACAO - SEM VALOR FISCAL'
            cnpj = '99999999000191'
        else:
            xnome = invoice.partner_id.legal_name[:60]

            if invoice.partner_id.is_company:
                ie = punctuation_rm(invoice.partner_id.inscr_est)

            if invoice.partner_id.country_id.id == \
                    invoice.company_id.country_id.id:
                if invoice.partner_id.is_company:
                    cnpj = punctuation_rm(invoice.partner_id.cnpj_cpf)
                else:
                    cpf = punctuation_rm(invoice.partner_id.cnpj_cpf)

        id_estrangeiro = None
        if invoice.partner_id.country_id.id != \
                invoice.company_id.country_id.id:
            id_estrangeiro = punctuation_rm(
                invoice.partner_id.cnpj_cpf)

        nfe_dest = self.leiauteNFe.destType(
            CNPJ=cnpj,
            CPF=cpf,
            idEstrangeiro=id_estrangeiro,
            xNome=xnome,
            enderDest=nfe_ender_dest,
            indIEDest=(
                int(invoice.partner_id.
                    partner_fiscal_type_id.ind_ie_dest)),
            IE=ie,
            ISUF=None,
            IM=None,
            email=invoice.partner_id.email or None,
        )

        return nfe_dest

    def _details(self, invoice, invoice_line, index, nfe_di):
        """Detalhe"""

        dict_imposto = {}
        dict_det = {}

        cEAN = cEANTrib = None
        if invoice_line.product_id:
            cProd = (invoice_line.product_id.code or None),
            cEAN = (invoice_line.product_id.barcode or 'SEM GTIN')
            cEANTrib = (invoice_line.product_id.barcode or None)
            xProd = invoice_line.product_id.name[:120] or None
        else:
            cProd = invoice_line.product_id.code or None
            xProd = invoice_line.product_id.name[:120] or None

        vUnCom = vUnTrib = vProd = vFrete = vDesc = vOutro = vSeg = None
        if invoice_line.price_unit:
            vUnCom = str("%.7f" % invoice_line.price_unit)
            vUnTrib = str("%.7f" % invoice_line.price_unit)
        if invoice_line.price_gross:
            vProd = str("%.2f" % invoice_line.price_gross)
        if invoice_line.freight_value:
            vFrete = str("%.2f" % invoice_line.freight_value)

        if invoice_line.discount_value:
            vDesc = str("%.2f" % invoice_line.discount_value)

        if invoice_line.other_costs_value:
            vOutro = str("%.2f" % invoice_line.other_costs_value)

        if invoice_line.insurance_value:
            vSeg = str("%.2f" % invoice_line.insurance_value)

        # TODO - Check if its right
        if invoice_line.fiscal_classification_id.code:
             extipi = punctuation_rm(
                 invoice_line.fiscal_classification_id.code or '')[:3]

        dict_det['prod'] = self.leiauteNFe.prodType(
            cPRod=cProd,
            cEAN=cEAN,
            xProd=xProd,
            NCM=punctuation_rm(
                invoice_line.fiscal_classification_id.code or '')[:8],
            CEST=punctuation_rm(invoice_line.cest_id.code or '') or None,
            indEscala=None,
            CNPJFab=None,
            cBenef=None,
            EXTIPI=extipi,
            CFOP=invoice_line.cfop_id.code,
            uCom=invoice_line.uom_id.name[:2] or None,
            qCom=str("%.4f" % invoice_line.quantity),
            vUnCom=vUnCom,
            vProd=vProd,
            cEANTrib=cEANTrib,
            uTrib=invoice_line.uom_id.name[:2] or None,
            qTrib=str("%.4f" % invoice_line.quantity)[:2],
            vUnTrib=vUnTrib,
            vFrete=vFrete,
            vSeg=vSeg,
            vDesc=vDesc,
            vOutro=vOutro,
            intTot=1,
            DI=nfe_di,
        )

        #
        # Produto entra no total da NF-e
        #

        if invoice_line.product_type == 'product':
            # ICMS
            icms_dict = {}
            vBC = pICMS = vICMS = pFCP = vFCP = None
            if invoice_line.icms_base:
                vBC = str("%.2f" % invoice_line.icms_base)
            if invoice_line.icms_percent:
                pICMS = str("%.2f" % invoice_line.icms_percent)
            if invoice_line.icms_value:
                vICMS = str("%.2f" % invoice_line.icms_value)
            if invoice_line.icms_fcp_percent:
                pFCP = str("%.2f" % invoice_line.icms_fcp_percent)
            if invoice_line.icms_fcp_value:
                vFCP = str("%.2f" % invoice_line.icms_fcp_value)

            if invoice_line.icms_cst_id.code == '00':
                icms_dict['icms00'] = self.leiauteNFe.ICMS00Type(
                    orig=(invoice_line.icms_origin),
                    CST=(invoice_line.icms_cst_id.code),
                    modBC=invoice_line.icms_base_type,
                    vBC=vBC,
                    pICMS=pICMS,
                    vICMS=vICMS,
                    pFCP=pFCP,
                    vFCP=vFCP,
                )

            vBCFCP = pMVAST = pRedBCST = vBCST = pICMSST = vICMSST = \
                vBCFCPST = pFCPST = vFCPST = None

            # TODO - Campo não encontrado, criar ?
            # if invoice_line.icms_fcp_base:
            #    vBCFCP = str("%.2f" % invoice_line.icms_fcp_base)

            if invoice_line.icms_st_mva:
                pMVAST = str("%.2f" % invoice_line.icms_st_mva)

            if invoice_line.icms_st_percent_reduction:
                pRedBCST = str(
                    "%.2f" % invoice_line.icms_st_percent_reduction)

            if invoice_line.icms_st_base:
                vBCST = str("%.2f" % invoice_line.icms_st_base)

            if invoice_line.icms_st_percent:
                pICMSST = str("%.2f" % invoice_line.icms_st_percent)

            if invoice_line.icms_st_value:
                vICMSST = str("%.2f" % invoice_line.icms_st_value)

            # TODO - Campo não encontrado, criar ?
            # if invoice_line.icms_fcpst_base:
            #    vBCFCPST = str("%.2f" % invoice_line.icms_fcpst_base)

            # # TODO - Campo não encontrado, criar ?
            # if invoice_line.icms_fcpst_percent:
            #    pFCPST = str("%.2f" % invoice_line.icms_fcpst_percent)

            # TODO - Campo não encontrado, criar ?
            # if invoice_line.icms_fcpst_value:
            #    vFCPST = str("%.2f" % invoice_line.icms_fcpst_value)

            if invoice_line.icms_cst_id.code == '10':
                icms_dict['icms10'] = self.nfe.ICMS10Type(
                    orig=invoice_line.icms_origin,
                    CST=invoice_line.icms_cst_id.code,
                    modBC=invoice_line.icms_base_type,
                    vBC=vBC,
                    pICMS=pICMS,
                    vICMS=vICMS,
                    vBCFCP=vBCFCP,
                    pFCP=pFCP,
                    vFCP=vFCP,
                    pMVAST=pMVAST,
                    modBCST=invoice_line.icms_st_base_type,
                    pRedBCST=pRedBCST,
                    vBCST=vBCST,
                    pICMSST=pICMSST,
                    vICMSST=vICMSST,
                    vBCFCPST=vBCFCPST,
                    pFCPST=pFCPST,
                    vFCPST=vFCPST,
                )

            pRedBC = None

            if invoice_line.icms_percent_reduction:
                pRedBC = str(
                    "%.2f" % invoice_line.icms_percent_reduction)

            if invoice_line.icms_cst_id.code == '20':
                icms_dict['icms20'] = self.leiauteNFe.ICMS20Type(
                    orig=invoice_line.icms_origin,
                    CST=invoice_line.icms_cst_id.code,
                    modBC=invoice_line.icms_base_type,
                    vBC=vBC,
                    pRedBC=pRedBC,
                    pICMS=pICMS,
                    vICMS=vICMS,
                    vBCFCP=vBCFCP,
                    pFCP=pFCP,
                    vFCP=vFCP,
                    motDesICMS=invoice_line.icms_relief_id.code,
                    # TODO ?
                    # vICMSDeson= ?,
                )
            if invoice_line.icms_cst_id.code == '30':
                icms_dict['icms30'] = self.leiauteNFe.ICMS30Type(
                    orig=invoice_line.icms_origin,
                    CST=invoice_line.icms_cst_id.code,
                    vBC=vBC,
                    pICMS=pICMS,
                    vICMS=vICMS,
                    vBCFCP=vBCFCP,
                    pFCP=pFCP,
                    vFCP=vFCP,
                    motDesICMS=invoice_line.icms_relief_id.code,
                    # TODO ?
                    # vICMSDeson=???,
                    modBCST=invoice_line.icms_st_base_type,
                    pRedBCST=pRedBCST,
                    vBCST=vBCST,
                    pICMSST=pICMSST,
                    vICMSST=vICMSST,
                    vBCFCPST=vBCFCPST,
                    pFCPST=pFCPST,
                    vFCPST=vFCPST,
                )
            if invoice_line.icms_cst_id.code == '51':
                icms_dict['icms51'] = self.leiauteNFe.ICMS51Type(
                    orig=invoice_line.icms_origin,
                    CST=invoice_line.icms_cst_id.code,
                    vBC=vBC,
                    pRedBC=pRedBC,
                    pICMS=pICMS,
                    vICMS=vICMS,
                    vBCFCP=vBCFCP,
                    pFCP=pFCP,
                    vFCP=vFCP,
                    motDesICMS=invoice_line.icms_relief_id.code,
                    # TODO ?
                    # vICMSOp= ???,
                    # vICMSDeson=???,
                    # pDif= ????,
                    # vICMSDif= ???,
                )
            if invoice_line.icms_cst_id.code == '60':
                icms_dict['icms60'] = self.leiauteNFe.ICMS60Type(
                    orig=invoice_line.icms_origin,
                    CST=invoice_line.icms_cst_id.code,
                    # TODO ?
                    # vBCSTRet = ???,
                    # pST = ??? ,
                    # vICMSSTRet = ??? ,
                    # vBCFCPSTRet = ??? ,
                    # pFCPSTRet = ???,
                    # vFCPSTRet = ??? ,
                    # pRedBCEfet = ??? ,
                    # vBCEfet = ??? ,
                    # pICMSEfet = ??? ,
                    # vICMSEfet = ??? ,
                )
            if invoice_line.icms_cst_id.code == '70':
                icms_dict['icms70'] = self.leiauteNFe.ICMS70Type(
                    orig=invoice_line.icms_origin,
                    CST=invoice_line.icms_cst_id.code,
                    modBC=invoice_line.icms_base_type,
                    pRedBC=pRedBC,
                    vBC=vBC,
                    pICMS=pICMS,
                    vICMS=vICMS,
                    vBCFCP=vBCFCP,
                    pFCP=pFCP,
                    vFCP=vFCP,
                    modBCST=invoice_line.icms_st_base_type,
                    pMVAST=pMVAST,
                    pRedBCST=pRedBCST,
                    vBCST=vBCST,
                    pICMSST=pICMSST,
                    vICMSST=vICMSST,
                    vBCFCPST=vBCFCPST,
                    pFCPST=pFCPST,
                    vFCPST=vFCPST,
                    motDesICMS=invoice_line.icms_relief_id.code,
                    # TODO ?
                    # vICMSDeson=???,
                )
            if invoice_line.icms_cst_id.code == '90':
                icms_dict['icms90'] = self.leiauteNFe.ICMS90Type(
                    orig=invoice_line.icms_origin,
                    CST=invoice_line.icms_cst_id.code,
                    modBC=invoice_line.icms_base_type,
                    vBC=vBC,
                    pRedBC=pRedBC,
                    pICMS=pICMS,
                    vICMS=vICMS,
                    vBCFCP=vBCFCP,
                    pFCP=pFCP,
                    vFCP=vFCP,
                    modBCST=invoice_line.icms_st_base_type,
                    pMVAST=pMVAST,
                    pRedBCST=pRedBCST,
                    vBCST=vBCST,
                    pICMSST=pICMSST,
                    vICMSST=vICMSST,
                    vBCFCPST=vBCFCPST,
                    pFCPST=pFCPST,
                    vFCPST=vFCPST,
                    motDesICMS=invoice_line.icms_relief_id.code,
                    # TODO ?
                    # vICMSDeson=???,
                )

            # Informação do ICMS Interestadual nas vendas para
            # consumidor final
            if invoice.ind_final == '1':
                icms_dict['icmspart'] = self.leiauteNFe.ICMSPartType(
                    orig=(invoice_line.icms_origin),
                    CST=(invoice_line.icms_cst_id.code),
                    modBC=invoice_line.icms_base_type,
                    vBC=str("%.2f" % invoice_line.icms_base),
                    pRedBC=str(
                        "%.2f" % invoice_line.icms_percent_reduction),
                    pICMS=str("%.2f" % invoice_line.icms_percent),
                    vICMS=str("%.2f" % invoice_line.icms_value),
                    modBCST=(invoice_line.icms_st_base_type),
                    pMVAST=str("%.2f" % invoice_line.icms_st_mva),
                    pRedBCST=str(
                        "%.2f" % invoice_line.icms_st_percent_reduction),
                    vBCST=str("%.2f" % invoice_line.icms_st_base),
                    pICMSST=str("%.2f" % invoice_line.icms_st_percent),
                    vICMSST=str("%.2f" % invoice_line.icms_st_value),
                    # TODO ?
                    # pBCOp = ???,
                    # UFST = ???,
                )
                icms_dict['icmsufdest'] = self.leiauteNFe.ICMSUFDestType(
                    vBCUFDest=str("%.2f" % invoice_line.icms_dest_base),
                    pFCPUFDest=str("%.2f" % invoice_line.icms_fcp_percent),
                    pICMSUFDest=str("%.2f" % invoice_line.icms_dest_percent),
                    pICMSInter=str("%.2f" % invoice_line.icms_origin_percent),
                    pICMSInterPart=str(
                        "%.2f" % invoice_line.icms_part_percent),
                    vFCPUFDest=str("%.2f" % invoice_line.icms_fcp_value),
                    vICMSUFDest=str("%.2f" % invoice_line.icms_dest_value),
                    vICMSUFRemet=str("%.2f" % invoice_line.icms_origin_value),

                )

            if invoice_line.icms_cst_id.code in (
                    '10', '30', '70', '90', '201', '202', '500', '900'):
                icms_dict['icmsst'] = self.leiauteNFe.ICMSSTType(
                    orig=(invoice_line.icms_origin),
                    CST=(invoice_line.icms_cst_id.code),
                    # TODO - ?
                    # vBCSTRet = ???,
                    # vICMSSTRet = ??? ,
                    # vBCSTDest = ???,
                    # vICMSSTDest = ???,
                )

            if invoice_line.icms_cst_id.code == '101':
                icms_dict['icmssn101'] = self.leiauteNFe.ICMSSN101Type(
                    orig=(invoice_line.icms_origin),
                    CSOSN=invoice_line.icms_cst_id.code,
                    pCredSN=str("%.2f" % invoice_line.icms_percent),
                    vCredICMSSN=str("%.2f" % invoice_line.icms_value),
                )
            if invoice_line.icms_cst_id.code == '102':
                icms_dict['icmssn102'] = self.leiauteNFe.ICMSSN102Type(
                    orig=(invoice_line.icms_origin),
                    CSOSN=invoice_line.icms_cst_id.code,
                )
            if invoice_line.icms_cst_id.code == '201':
                icms_dict['icmssn201'] = self.leiauteNFe.ICMSSN201Type(
                    orig=(invoice_line.icms_origin),
                    CSOSN=invoice_line.icms_cst_id.code,
                    modBCST=(invoice_line.icms_st_base_type),
                    pMVAST=str("%.2f" % invoice_line.icms_st_mva),
                    pRedBCST=str(
                        "%.2f" % invoice_line.icms_st_percent_reduction),
                    vBCST=str("%.2f" % invoice_line.icms_st_base),
                    pICMSST=str("%.2f" % invoice_line.icms_st_percent),
                    vICMSST=str("%.2f" % invoice_line.icms_st_value),
                    vBCFCPST=str("%.2f" % invoice_line.icms_fcpst_base),
                    pFCPST=str("%.2f" % invoice_line.icms_fcpst_percent),
                    vFCPST=str("%.2f" % invoice_line.icms_fcpst_value),
                    pCredSN=str("%.2f" % invoice_line.icms_percent),
                    vCredICMSSN=str("%.2f" % invoice_line.icms_value),
                )
            if invoice_line.icms_cst_id.code == '202':
                icms_dict['icmssn202'] = self.leiauteNFe.ICMSSN202Type(
                    orig=(invoice_line.icms_origin),
                    CSOSN=invoice_line.icms_cst_id.code,
                    modBCST=(invoice_line.icms_st_base_type),
                    pMVAST=str("%.2f" % invoice_line.icms_st_mva),
                    pRedBCST=str(
                        "%.2f" % invoice_line.icms_st_percent_reduction),
                    vBCST=str("%.2f" % invoice_line.icms_st_base),
                    pICMSST=str("%.2f" % invoice_line.icms_st_percent),
                    vICMSST=str("%.2f" % invoice_line.icms_st_value),
                    vBCFCPST=str("%.2f" % invoice_line.icms_fcpst_base),
                    pFCPST=str("%.2f" % invoice_line.icms_fcpst_percent),
                    vFCPST=str("%.2f" % invoice_line.icms_fcpst_value),
                )
            if invoice_line.icms_cst_id.code == '500':
                icms_dict['icms500'] = self.leiauteNFe.ICMSSN500Type(
                    orig=(invoice_line.icms_origin),
                    CSOSN=invoice_line.icms_cst_id.code,
                    # TODO - ?
                    # vBCSTRet = ???,
                    # pST = ??? ,
                    # vICMSSTRet = ??? ,
                    # vBCFCPSTRet = ??? ,
                    # pFCPSTRet = ???,
                    # vFCPSTRet = ??? ,
                    # pRedBCEfet = ??? ,
                    # vBCEfet = ??? ,
                    # pICMSEfet = ??? ,
                    # vICMSEfet = ??? ,
                )
            if invoice_line.icms_cst_id.code == '900':
                icms_dict['icmssn900'] = self.leiauteNFe.ICMSSN900Type(
                    orig=(invoice_line.icms_origin),
                    CST=(invoice_line.icms_cst_id.code),
                    modBC=invoice_line.icms_base_type,
                    vBC=str("%.2f" % invoice_line.icms_base),
                    pRedBC=str(
                        "%.2f" % invoice_line.icms_percent_reduction),
                    pICMS=str("%.2f" % invoice_line.icms_percent),
                    vICMS=str("%.2f" % invoice_line.icms_value),
                    vBCFCP=str("%.2f" % invoice_line.icms_fcp_base),
                    pFCP=str("%.2f" % invoice_line.icms_fcp_percent),
                    vFCP=str("%.2f" % invoice_line.icms_fcp_value),
                    modBCST=(invoice_line.icms_st_base_type),
                    pMVAST=str("%.2f" % invoice_line.icms_st_mva),
                    pRedBCST=str(
                        "%.2f" % invoice_line.icms_st_percent_reduction),
                    vBCST=str("%.2f" % invoice_line.icms_st_base),
                    pICMSST=str("%.2f" % invoice_line.icms_st_percent),
                    vICMSST=str("%.2f" % invoice_line.icms_st_value),
                    vBCFCPST=str("%.2f" % invoice_line.icms_fcpst_base),
                    pFCPST=str("%.2f" % invoice_line.icms_fcpst_percent),
                    vFCPST=str("%.2f" % invoice_line.icms_fcpst_value),
                    pCredSN=str("%.2f" % invoice_line.icms_percent),
                    vCredICMSSN=str("%.2f" % invoice_line.icms_value),
                )

            dict_imposto['ICMS'] = self.leiauteNFe.ICMSType(
                ICMS00=icms_dict.get('icms00'),
                ICMS10=icms_dict.get('icms10'),
                ICMS20=icms_dict.get('icms20'),
                ICMS30=icms_dict.get('icms30'),
                ICMS51=icms_dict.get('icms51'),
                ICMS60=icms_dict.get('icms60'),
                ICMS70=icms_dict.get('icms70'),
                ICMS90=icms_dict.get('icms90'),
                ICMSPart=icms_dict.get('icmspart'),
                ICMSST=icms_dict.get('icmsst'),
                ICMSSN101=icms_dict.get('icms101'),
                ICMSSN102=icms_dict.get('icms102'),
                ICMSSN201=icms_dict.get('icms201'),
                ICMSSN202=icms_dict.get('icms202'),
                ICMSSN500=icms_dict.get('icms500'),
                ICMSSN900=icms_dict.get('icms900'),
            )

            # IPI
            # IPITribType

            ipi_vBC = ipi_pIPI = ipi_qUnid = ipi_vUnid = ipi_vIPI = None

            if invoice_line.ipi_type == 'percent' or '':

                if invoice_line.ipi_base:
                    ipi_vBC = str(
                        "%.2f" % invoice_line.ipi_base)
                if invoice_line.ipi_percent:
                    ipi_pIPI = str(
                        "%.2f" % invoice_line.ipi_percent)

            if invoice_line.ipi_type == 'quantity':

                if invoice_line.product_id:

                    if invoice_line.quantity:
                        pesol = invoice_line.product_id.weight_net
                        ipi_qUnid = str(
                            "%.2f" % invoice_line.quantity * pesol)
                    if invoice_line.ipi_percent:
                        ipi_vUnid = str(
                            "%.2f" % invoice_line.ipi_percent)

            ipi_cEnq = str(
                invoice_line.ipi_guideline_id.code or '999').zfill(3)

            if invoice_line.ipi_value:
                ipi_vIPI = str("%.2f" % invoice_line.ipi_value)

            ipi_Trib = self.leiauteNFe.IPITribType(
                CST=invoice_line.ipi_cst_id.code,
                vBC=ipi_vBC,
                pIPI=ipi_pIPI,
                qUnid=ipi_qUnid,
                vUnid=ipi_vUnid,
                vIPI=ipi_vIPI,
            )
            ipi_NT = self.leiauteNFe.IPITribType(
                CST=invoice_line.ipi_cst_id.code,
            )
            dict_imposto['TIPI'] = self.leiauteNFe.TIpi(
                CNPJProd=None,
                cSelo=None,
                qSelo=None,
                cEnq=ipi_cEnq,
                IPITrib=ipi_Trib,
                IPINT=ipi_NT,
            )

        else:
            # ISSQN
            dict_imposto['ISSQN'] = self.leiauteNFe.ISSQNType(
                vBC=str("%.2f" % invoice_line.issqn_base),
                vAliq=str("%.2f" % invoice_line.issqn_percent),
                vISSQN=str("%.2f" % invoice_line.issqn_value),
                cMunFG=('%s%s') % (
                    invoice.partner_id.state_id.ibge_code,
                    invoice.partner_id.l10n_br_city_id.ibge_code
                ),
                cListServ=punctuation_rm(
                    invoice_line.service_type_id.code),
                cSitTrib=invoice_line.issqn_type,
            )

        # PIS
        dict_pis = {}

        pis_vBC = pis_pPIS = pis_vPIS = None

        if invoice_line.pis_base:
            pis_vBC = str("%.2f" % invoice_line.pis_base)
        if invoice_line.pis_percent:
            pis_pPIS = str("%.2f" % invoice_line.pis_percent)
        if invoice_line.pis_value:
            pis_vPIS = str("%.2f" % invoice_line.pis_value)

        if invoice_line.pis_cst_id.code in ('01', '02'):
            dict_pis['PISAliq'] = self.leiauteNFe.PISAliqType(
                CST=invoice_line.pis_cst_id.code,
                vBC=pis_vBC,
                pPIS=pis_pPIS,
                vPIS=pis_vPIS,
            )
        if invoice_line.pis_cst_id.code == '03':
            dict_pis['PISQtde'] = self.leiauteNFe.PISQtdeType(
                CST=invoice_line.pis_cst_id.code,
                qBCProd=None,
                vBC=pis_vBC,
                vAliqProd=None,
                vPIS=pis_vPIS,
            )
        if invoice_line.pis_cst_id.code in (
                '04', '06', '07', '08', '09'):
            dict_pis['PISNT'] = self.leiauteNFe.PISNTType(
                CST=invoice_line.pis_cst_id.code,
            )
        if invoice_line.pis_cst_id.code == '99':
            dict_pis['PISOutr'] = self.leiauteNFe.PISOutrType(
                CST=invoice_line.pis_cst_id.code,
                vBC=pis_vBC,
                pPIS=pis_pPIS,
                qBCProd=None,
                vAliqProd=None,
                vPIS=pis_vPIS,
            )

        pis_vBCST = pis_pPISST = pis_vPISST = None

        if invoice_line.pis_st_base:
            pis_vBCST = str("%.2f" % invoice_line.pis_st_base)
        if invoice_line.pis_st_percent:
            pis_pPISST = str("%.2f" % invoice_line.pis_st_percent)
        if invoice_line.pis_st_value:
            pis_vPISST = str("%.2f" % invoice_line.pis_st_value)

        dict_pis['PISST'] = self.leiauteNFe.PISSTType(
            vBC=pis_vBCST,
            pPIS=pis_pPISST,
            qBCProd=None,
            vAliqProd=None,
            vPIS=pis_vPISST,
        )

        dict_imposto['PIS'] = self.leiauteNFe.PISType(
            PISAliq=dict_pis.get('PISAliq'),
            PISQtde=dict_pis.get('PISQtde'),
            PISNT=dict_pis.get('PISNT'),
            PISOutr=dict_pis.get('PISOutr'),
        )

        # COFINS
        dict_cofins = {}

        cofins_vBC = cofins_pCOFINS = cofins_vCOFINS = None

        if invoice_line.cofins_base:
            cofins_vBC = str("%.2f" % invoice_line.cofins_base)
        if invoice_line.cofins_percent:
            cofins_pCOFINS = str("%.2f" % invoice_line.cofins_percent)
        if invoice_line.cofins_value:
            cofins_vCOFINS = str("%.2f" % invoice_line.cofins_value)


        if invoice_line.cofins_cst_id.code in ('01', '02'):
            dict_cofins['COFINSAliq'] = self.leiauteNFe.COFINSAliqType(
                CST=invoice_line.cofins_cst_id.code,
                vBC=cofins_vBC,
                pCOFINS=cofins_pCOFINS,
                vCOFINS=cofins_vCOFINS,
            )
        if invoice_line.cofins_cst_id.code == '03':
            dict_cofins['COFINSQtde'] = self.leiauteNFe.COFINSQtdeType(
                CST=invoice_line.cofins_cst_id.code,
                qBCProd=None,
                vAliqProd=None,
                vCOFINS=cofins_vCOFINS,
            )
        if invoice_line.cofins_cst_id.code in (
                '04', '06', '07', '08', '09'):
            dict_cofins['COFINSNT'] = self.leiauteNFe.COFINSNTType(
                CST=invoice_line.pis_cst_id.code,
            )
        if invoice_line.cofins_cst_id.code in (
                '49', '50', '51', '52', '53', '54', '55', '56', '60', '61',
                '62', '63', '64', '65', '67', '70', '71', '72', '73', '74',
                '75', '98', '99'):
            dict_cofins['COFINSOutrType'] = self.leiauteNFe.COFINSOutrType(
                CST=invoice_line.cofins_cst_id.code,
                vBC=cofins_vBC,
                pCOFINS=cofins_pCOFINS,
                qBCProd=None,
                vAliqProd=None,
                vCOFINS=cofins_vCOFINS,
            )

        # COFINSST

        cofins_vBCST = cofins_pCOFINSST = cofins_vCOFINSST = None

        if invoice_line.cofins_st_base:
            cofins_vBCST = str("%.2f" % invoice_line.cofins_st_base)
        if invoice_line.cofins_st_percent:
            cofins_pCOFINSST = str("%.2f" % invoice_line.cofins_st_percent)
        if invoice_line.cofins_st_value:
            cofins_vCOFINSST = str("%.2f" % invoice_line.cofins_st_value)

        dict_cofins['COFINSST'] = self.leiauteNFe.COFINSSTType(
            vBC=cofins_vBCST,
            pCOFINS=cofins_pCOFINSST,
            qBCProd=None,
            vAliqProd=None,
            vCOFINS=cofins_vCOFINSST,
        )

        dict_imposto['COFINS'] = self.leiauteNFe.COFINSType(
            COFINSAliq=dict_cofins.get('COFINSAliq'),
            COFINSQtde=dict_cofins.get('COFINSQtde'),
            COFINSNT=dict_cofins.get('COFINSNT'),
            COFINSOutr=dict_cofins.get('COFINSOutr'),
        )

        # II IIType
        # TODO - put if to include TAG
        # dict_imposto['II'] = self.leiauteNFe.IIType(
        #     vBC=str("%.2f" % invoice_line.ii_base),
        #     vDespAdu=str("%.2f" % invoice_line.ii_customhouse_charges),
        #     vII=str("%.2f" % invoice_line.ii_value),
        #     vIOF=str("%.2f" % invoice_line.ii_iof),
        # )

        dict_det['imposto'] = self.leiauteNFe.impostoType(
            vTotTrib=str("%.2f" % invoice_line.total_taxes),
            ICMS=dict_imposto.get('ICMS'),
            II=dict_imposto.get('II'),
            IPI=dict_imposto.get('IPI'),
            ISSQN=dict_imposto.get('ISSSQN'),
            PIS=dict_imposto['PIS'],
            PISST=dict_imposto.get('PISST'),
            COFINS=dict_imposto.get('COFINS'),
            COFINSST=dict_imposto.get('COFINSST'),
            ICMSUFDest=dict_imposto.get('ICMSUFDest')
        )

        dict_imposto['impostoDevol'] = None
        # TODO - put if to include TAG
        # dict_det['impostoDevol'] = self.leiauteNFe.impostoDevolType(
        #     pDevol=None,
        #     IPI=dict_ipi.get('IPI'),
        # )

        nfe_det = self.leiauteNFe.detType(
            nItem=index,
            prod=dict_det.get('prod'),
            imposto=dict_det.get('imposto'),
            impostoDevol=dict_det.get('impostoDevol'),
            infAdProd=invoice_line.fiscal_comment or None,
        )

        return nfe_det

    def _di(self, invoice_line_di, nfe_di_adi):

        nfe_di = self.leiauteNFe.DIType(
            nDI=invoice_line_di.name,
            dDI=invoice_line_di.date_registration or None,
            xLocDesemb=invoice_line_di.location,
            UFDesemb=invoice_line_di.state_id.code or None,
            dDesemb=invoice_line_di.date_release or None,
            tpViaTransp=invoice_line_di.type_transportation or None,
            vAFRMM=str("%.2f" % invoice_line_di.afrmm_value) or None,
            tpIntermedio=invoice_line_di.type_import or None,
            CNPJ=invoice_line_di.exporting_code or None,
            UFTerceiro=invoice_line_di.thirdparty_state_id.code or None,
            cExportador=invoice_line_di.exporting_code or None,
            adi=nfe_di_adi
        )

        return nfe_di

    def _addition(self, invoice_line_di):
        nfe_di_adi = self.leiauteNFe.adiType(
            nAdicao=invoice_line_di.name,
            nSeqAdic=invoice_line_di.sequence,
            cFabricante=invoice_line_di.manufacturer_code,
            vDescDI=str("%.2f" % invoice_line_di.amount_discount),
            nDraw=None,
        )
        return nfe_di_adi

    def _encashment_data(self, invoice):
        """Dados de Cobrança"""

        if invoice.journal_id.revenue_expense:
            numero_dup = 0
            nfe_dup_list = []
            for move_line in invoice.move_line_receivable_id:
                numero_dup += 1

                if invoice.type in ('out_invoice', 'in_refund'):
                    value = move_line.debit
                else:
                    value = move_line.credit

                # dup = self._get_Dup()

                nfe_dup = self.leiauteNFe.dupType(
                    nDup=str(numero_dup).zfill(3),
                    dVenc=(move_line.date_maturity or
                               invoice.date_due or
                               invoice.date_invoice),
                    vDup=str("%.2f" % value),
                )
                nfe_dup_list.append(nfe_dup)

        nfe_fat = self.leiauteNFe.fatType(
            nFat=invoice.fiscal_number,
            vOrig=str("%.2f" % invoice.amount_total),
            # TODO - ?
            vDesc=None,
            vLiq=str("%.2f" % invoice.amount_total),
        )

        nfe_cobr = self.leiauteNFe.cobrType(
            fat=nfe_fat,
            dup=nfe_dup_list,
        )

        return nfe_cobr

    def _carrier_data(self, invoice, nfe_vol):
        """Dados da Transportadora e veiculo"""

        nfe_transporta = None
        # if invoice.carrier_id:
        #
        #     CNPJ = CPF = None
        #     if invoice.carrier_id.partner_id.is_company:
        #         CNPJ = punctuation_rm(
        #             invoice.carrier_id.partner_id.cnpj_cpf or None)
        #     else:
        #         CPF = punctuation_rm(
        #             invoice.carrier_id.partner_id.cnpj_cpf or None)
        #
        #     nfe_transporta = self.leiauteNFe.transportaType(
        #         CNPJ=CNPJ,
        #         CPF=CPF,
        #         xNome=invoice.carrier_id.partner_id.legal_name[:60] or None,
        #         IE=punctuation_rm(
        #             invoice.carrier_id.partner_id.inscr_est),
        #         xEnder=invoice.carrier_id.partner_id.street or None,
        #         xMun=invoice.carrier_id.partner_id.l10n_br_city_id.name or None,
        #         UF=invoice.carrier_id.partner_id.state_id.code or None,
        #     )

        nfe_tveiculo = None
        # if invoice.vehicle_id:
        #     nfe_tveiculo = self.leiauteNFe.tveiculo(
        #         placa=invoice.vehicle_id.plate or None,
        #         UF=invoice.vehicle_id.plate.state_id.code or None,
        #         RNTC=invoice.vehicle_id.rntc_code or None,
        #     )

        nfe_transp = self.leiauteNFe.transpType(
            # modFrete=(invoice.incoterm and
            #          invoice.incoterm.freight_responsibility or '9'),
            modFrete=None,
            transporta=nfe_transporta,
            retTransp=None,
            veicTransp=nfe_tveiculo,
            reboque=None,
            vagao=None,
            balsa=None,
            vol=nfe_vol,
        )

        return nfe_transp

    def _weight_data(self, invoice):
        """Campos do Transporte da NF-e Bloco 381"""

        nfe_lacres = None
        # TODO - map field
        # nfe_lacres = [self.leiauteNFe.lacresType(
        #     nLacre=None
        # )]

        pesoL = pesoB = None
        if invoice.weight_net:
            pesoL = str("%.2f" % invoice.weight_net)
        if invoice.weight:
            pesoB = str("%.2f" % invoice.weight)

        nfe_vol = self.leiauteNFe.volType(
            qVol=invoice.number_of_packages or None,
            esp=invoice.kind_of_packages or None,
            marca=invoice.brand_of_packages or None,
            nVol=invoice.notation_of_packages or None,
            pesoL=pesoL,
            pesoB=pesoB,
            lacres=nfe_lacres
        )

        return nfe_vol

    def _additional_information(self, invoice):
        """Informações adicionais"""

        nfe_infadic = self.leiauteNFe.infAdicType(
            infAdFisco=invoice.fiscal_comment or None,
            infCpl=invoice.comment or None,
        )

        return nfe_infadic

    def _total(self, invoice):
        """Totais"""

        vBC = vICMS = vFCPUFDest = vICMSUFDest = vICMSUFRemet = vBCST = \
            vST = vProd = vFrete = vSeg = vDesc = vII = vIPI = vPIS = \
            vCOFINS = vOutro = vNF = vTotTrib = None
        if invoice.icms_base:
            vBC = str("%.2f" % invoice.icms_base)
        if invoice.icms_value:
            vICMS = str("%.2f" % invoice.icms_value)
        if invoice.icms_fcp_value:
            vFCPUFDest = str("%.2f" % invoice.icms_fcp_value)
        if invoice.icms_fcp_value:
            vICMSUFDest = str("%.2f" % invoice.icms_dest_value)
        if invoice.icms_origin_value:
            vICMSUFRemet = str("%.2f" % invoice.icms_origin_value)
        if invoice.icms_st_base:
            vBCST = str("%.2f" % invoice.icms_st_base)
        if invoice.icms_st_value:
            vST = str("%.2f" % invoice.icms_st_value)
        if invoice.amount_gross:
            vProd = str("%.2f" % invoice.amount_gross)
        if invoice.amount_freight:
            vFrete = str("%.2f" % invoice.amount_freight)
        if invoice.amount_insurance:
            vSeg = str("%.2f" % invoice.amount_insurance)
        if invoice.amount_discount:
            vDesc = str("%.2f" % invoice.amount_discount)
        if invoice.ii_value:
            vII = str("%.2f" % invoice.ii_value)
        if invoice.ipi_value:
            vIPI = str("%.2f" % invoice.ipi_value)
        if invoice.pis_value:
            vPIS = str("%.2f" % invoice.pis_value)
        if invoice.cofins_value:
            vCOFINS = str("%.2f" % invoice.cofins_value)
        if invoice.amount_costs:
            vOutro = str("%.2f" % invoice.amount_costs)
        if invoice.amount_total:
            vNF = str("%.2f" % invoice.amount_total)
        if invoice.amount_total_taxes:
            vTotTrib = str("%.2f" % invoice.amount_total_taxes)

        nfe_icms_total = self.leiauteNFe.ICMSTotType(
            vBC=vBC,
            vICMS=vICMS,
            vFCPUFDest=vFCPUFDest,
            vICMSUFDest=vICMSUFDest,
            vICMSUFRemet=vICMSUFRemet,
            vBCST=vBCST,
            vST=vST,
            vProd=vProd,
            vFrete=vFrete,
            vSeg=vSeg,
            vDesc=vDesc,
            vII=vII,
            vIPI=vIPI,
            vPIS=vPIS,
            vCOFINS=vCOFINS,
            vOutro=vOutro,
            vNF=vNF,
            vTotTrib=vTotTrib,
        )

        # TODO
        nfe_issqn_total = None
        # nfe_issqn_total = self.leiauteNFe.ISSQNtotType(
        #     vServ=None,
        #     vBC=None,
        #     vISS=None,
        #     vPIS=None,
        #     vCOFINS=None,
        #     dCompet=None,
        #     vDeducao=None,
        #     vOutro=None,
        #     vDescIncond=None,
        #     vDescCond=None,
        #     vISSRet=None,
        #     cRegTrib=None,
        # )

        # TODO - ?
        nfe_rettrib = None
        # nfe_rettrib = self.leiauteNFe.retTribType(
        #     vRetPIS=None,
        #     vRetCOFINS=None,
        #     vRetCSLL=None,
        #     vBCIRRF=None,
        #     vIRRF=None,
        #     vBCRetPrev=None,
        #     vRetPrev=None,
        # )

        nfe_total = self.leiauteNFe.totalType(
            ICMSTot=nfe_icms_total,
            ISSQNtot=nfe_issqn_total,
            retTrib=nfe_rettrib,
        )

        return nfe_total

    def _export(self, invoice):
        "Informações de exportação"
        nfe_export = self.leiauteNFe.exportaType(
            UFSaidaPais=invoice.shipping_state_id.code or None,
            xLocExporta=invoice.shipping_location or None,
            xLocDespacho=invoice.expedition_location or None,
        )

        return nfe_export

    def get_NFe(self):

        try:
            from nfelib.v4_00 import leiauteNFe
        except ImportError:
            raise UserError(
                _(u"Biblioteca NFeLIB não instalada!"))

        return leiauteNFe

    def get_xml(self, invoices, nfe_environment):
        """"""
        result = []

        for nfe in self._serializer(invoices, nfe_environment):
            result.append({
                # 'key': nfe.infNFe.Id.valor,
                'nfe': nfe})
        return result

    def set_xml(self, nfe_string, context=None):
        """"""
        nfe = self.get_NFe()
        nfe.set_xml(nfe_string)
        return nfe


class NFe310(NFe200):
    def __init__(self):
        super(NFe310, self).__init__()


class NFe400(NFe310):
    def __init__(self):
        super(NFe400, self).__init__()

    def _details_pag(self, invoice, pag):

        for pagamento in invoice.account_payment_ids:
            pag.detPag.append(self._payment_date(pagamento))

        pag.vTroco.valor = str("%.2f" % invoice.amount_change)

    def _payment_date(self, pagamento):

        pag = self._get_DetPag()

        # Somente no/ PL_009_V4_2016_002_v160b
        # pag.indPag.valor =
        # pagamento.payment_term_id.ind_forma_pagamento or ''

        pag.tPag.valor = pagamento.forma_pagamento
        pag.vPag.valor = str(pagamento.amount)

        if pagamento.forma_pagamento in FORMA_PAGAMENTO_CARTOES:
            pag.card.tpIntegra.valor = pagamento.card_integration
            pag.card.CNPJ.valor = punctuation_rm(pagamento.cnpj_cpf or '')
            pag.card.tBand.valor = pagamento.card_brand
            pag.card.cAut.valor = pagamento.autorizacao

        return pag

    def _encashment_data(self, invoice, cobr):
        """Dados de Cobrança"""

        if FORMA_PAGAMENTO_SEM_PAGAMENTO in \
                invoice.account_payment_ids.mapped('forma_pagamento'):
            return

        cobr.fat.nFat.valor = invoice.number
        cobr.fat.vOrig.valor = str("%.2f" % invoice.amount_payment_original)
        cobr.fat.vDesc.valor = str("%.2f" % invoice.amount_payment_discount)
        cobr.fat.vLiq.valor = str("%.2f" % invoice.amount_payment_net)

        for payment_line in invoice.account_payment_line_ids:
            dup = self._get_Dup()
            dup.nDup.valor = payment_line.number
            dup.dVenc.valor = payment_line.date_due
            dup.vDup.valor = str("%.2f" % payment_line.amount_net)
            cobr.dup.append(dup)

    def get_NFe(self):
        try:
            from nfelib.v4_00 import leiauteNFe
        except ImportError:
            raise UserError(
                _(u"Biblioteca NFeLIB não instalada!"))

        return leiuteNFe()

    def _get_NFRef(self):
        try:
            from pysped.nfe.leiaute import NFRef_400
        except ImportError:
            raise UserError(
                _(u"Biblioteca PySPED não instalada!"))

        return NFRef_400()

    def _get_Det(self):
        try:
            from pysped.nfe.leiaute import Det_400
        except ImportError:
            raise UserError(
                _(u"Biblioteca PySPED não instalada!"))
        return Det_400()
