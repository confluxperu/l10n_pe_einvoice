# -*- encoding: utf-8 -*-
from odoo import fields, api, models, _
import requests
import json
import datetime

import logging
log = logging.getLogger(__name__)


class LogisticDespatch(models.Model):
    _inherit = 'logistic.despatch'

    def action_open(self):
        res = super(LogisticDespatch, self).action_open()
        for despatch in self:
            picking = self.env['stock.picking'].search([('despatch_id','=', despatch.id)])
            if picking:
                picking[0].write({'numberg':despatch.name})
        return res

    def _l10n_pe_prepare_dte(self):
        res = super(LogisticDespatch, self)._l10n_pe_prepare_dte()
        res['origen_direccion'] = self.origin_address_id.direccion_complete_it
        res['destino_direccion'] = self.delivery_address_id.direccion_complete_it
        return res