import io
import csv
from datetime import date
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'scripts'))
import update_market_sources as u

class CollectorsTest(unittest.TestCase):
    def test_cepea_selects_paranagua_not_parana(self):
        html='''<h2>INDICADOR DA SOJA CEPEA/ESALQ - PARANAGUÁ</h2>
        <table><tr><th>Data</th><th>Valor R$</th><th>Var./Dia</th><th>Var./Mês</th><th>Valor US$</th></tr>
        <tr><td>20/10/2026</td><td>159,43</td><td>0,1%</td><td>0%</td><td>29,20</td></tr></table>
        <h2>INDICADOR DA SOJA CEPEA/ESALQ - PARANÁ</h2>
        <table><tr><th>Data</th><th>Valor R$</th></tr><tr><td>20/10/2026</td><td>148,90</td></tr></table>'''
        records = u.parse_cepea(html, today=date(2026,10,21))
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['brl_saca60'],159.43)
        self.assertEqual(records[0]['usd_saca60'],29.2)
    def test_cepea_rejects_future(self):
        html='<h2>Paranaguá</h2><table><tr><td>24/10/2026</td><td>159,43</td></tr></table>'
        with self.assertRaises(ValueError): u.parse_cepea(html, today=date(2026,10,21))
    def test_usda_filter(self):
        r=[{'Commodity_Code':'2222000','Country_Code':'BR','Market_Year':str(y),'Attribute_Description':a,'Value':'170000'} for y in range(2010,2028) for a in ('Production','Domestic Consumption','Exports')]
        r+=[{'Commodity_Code':'2222000','Country_Code':'US','Market_Year':str(y),'Attribute_Description':a,'Value':'110000'} for y in range(2010,2028) for a in ('Production','Domestic Consumption','Exports')]
        r+=[{'Commodity_Code':'0440000','Country_Code':'BR','Market_Year':'2026','Attribute_Description':'Production','Value':'9999'}]
        with patch.object(u, 'now_br', return_value=__import__('datetime').datetime(2026,10,21)):
            got=u.parse_usda_rows(r)
        self.assertEqual(len(got),108)
        self.assertTrue(all(item['pais'] in ('BR','US') for item in got))
    def test_valid_date(self):
        self.assertEqual(u.validate_day('14/10/2026',today=date(2026,10,21)),'2026-10-14')
        with self.assertRaises(ValueError): u.validate_day('01/02/2099',today=date(2026,10,21))

if __name__=='__main__':unittest.main()
