import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from datetime import date
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import update_data as u


class TestMacroeconomia(unittest.TestCase):
    def test_recalculo_macro_preserva_campos_e_estrutura(self):
        html=("const MACRO_ANUAL = {\n"
              "  2024: { ouro:2350, prata:28.3, cobre:9600, cdi:0.10, ipca:0.04, selic:0.12, diesel:5.6, custo:90 },\n"
              "  2026: { ouro:2800, prata:34.0, cobre:9700, cdi:0.14, ipca:0.05, selic:0.14, diesel:6, custo:95 },\n"
              "};\n")
        cdi=pd.DataFrame([{'data':pd.Timestamp('2024-12-31'),'valor':1}])
        ipca=pd.DataFrame([{'data':pd.Timestamp('2024-12-31'),'valor':0.5}])
        selic=pd.DataFrame([{'data':pd.Timestamp('2024-12-31'),'valor':11.75},
                            {'data':pd.Timestamp('2026-10-20'),'valor':12.25}])
        with patch.object(u,'fetch_bcb_sgs',side_effect=[cdi,ipca,selic]),patch.object(u,'date') as today:
            today.today.return_value=date(2026,10,21)
            out,ok=u.update_macro_anual(html)
        self.assertTrue(ok)
        self.assertIn('ouro:2350, prata:28.3, cobre:9600',out)
        self.assertIn('diesel:5.6, custo:90',out)
        self.assertIn('cdi:0.0100, ipca:0.0050, selic:0.1175',out)
        self.assertIn('2026: { ouro:2800',out)
        self.assertIn('selic:0.1225',out)
        self.assertIn('\n  2026:',out)

    def test_preserva_tudo_quando_api_falha(self):
        html='const MACRO_ANUAL = {\n  2025: { cdi:0.12, ipca:0.04 },\n};'
        with patch.object(u,'fetch_bcb_sgs',side_effect=RuntimeError('fora')):
            out,ok=u.update_macro_anual(html)
        self.assertFalse(ok)
        self.assertEqual(out,html)


if __name__=='__main__':
    unittest.main()
