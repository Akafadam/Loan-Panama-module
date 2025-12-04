# -*- coding: utf-8 -*-
# from odoo import http


# class LoanPanamaCustom(http.Controller):
#     @http.route('/loan_panama_custom/loan_panama_custom', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/loan_panama_custom/loan_panama_custom/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('loan_panama_custom.listing', {
#             'root': '/loan_panama_custom/loan_panama_custom',
#             'objects': http.request.env['loan_panama_custom.loan_panama_custom'].search([]),
#         })

#     @http.route('/loan_panama_custom/loan_panama_custom/objects/<model("loan_panama_custom.loan_panama_custom"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('loan_panama_custom.object', {
#             'object': obj
#         })

