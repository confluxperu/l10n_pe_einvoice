# -*- coding: utf-8 -*-
{
    'name': "Account Fix Tax (Price include)",
    'summary': """
        Overwrite methods on tax calculation.""",

    'description': """
        Overwrite methods on tax calculation.
    """,
    'author': "Conflux",
    'website': "https://conflux.pe",
    'category': 'Account',
    'version': '14.0.1.0.0',
    'depends': ['base','account'],
    'data': [
        "views/res_config_settings_view.xml",
        "views/account_move_view.xml",
    ],
}