import pya
ly = pya.Layout(); ly.dbu = 0.001
c = ly.create_cell("NEG_ML1_SPACE")
c.shapes(ly.layer(8, 0)).insert(pya.Box(0, 0, 2000, 2000))
c.shapes(ly.layer(8, 0)).insert(pya.Box(2500, 0, 4500, 2000))   # 0.5 um space
ly.write("/tmp/neg_ml1.gds")
print("built NEG_ML1_SPACE (0.5 um metal1 space)")
