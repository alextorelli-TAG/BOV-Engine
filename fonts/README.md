# Fonts

`FrankRuhlLibre[wght].ttf` is the upstream variable font from google/fonts
(OFL). The four static instances beside it were produced with:

    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    for name, wght in [('Regular',400),('Medium',500),('Bold',700),('Black',900)]:
        g = TTFont('FrankRuhlLibre[wght].ttf')
        instantiateVariableFont(g, {'wght': wght}, inplace=True, updateFontNames=True)
        g.save(f'FrankRuhlLibre-{name}.ttf')

`updateFontNames=True` matters. Without it all four instances keep the variable
font's name table, every weight reports as "Regular" in the output PDF, and you
cannot tell from the file whether bold actually applied.

Roboto is still missing — the google/fonts static paths 404'd. It is used only
in small corporate labels, not on any plate built so far. Fetch it before
building plates that need it.
