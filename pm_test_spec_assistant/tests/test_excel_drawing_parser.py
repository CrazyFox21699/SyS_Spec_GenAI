from __future__ import annotations

import zipfile

from openpyxl import Workbook

from src.parsers.excel_parser import extract_excel_workbook


DRAWING_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
          xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <xdr:twoCellAnchor>
    <xdr:from><xdr:col>7</xdr:col><xdr:row>1</xdr:row></xdr:from>
    <xdr:to><xdr:col>10</xdr:col><xdr:row>10</xdr:row></xdr:to>
    <xdr:sp>
      <xdr:nvSpPr><xdr:cNvPr id="1" name="State_OFF"/></xdr:nvSpPr>
      <xdr:spPr><a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom></xdr:spPr>
      <xdr:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>OFF</a:t></a:r></a:p></xdr:txBody>
    </xdr:sp>
    <xdr:clientData/>
  </xdr:twoCellAnchor>
  <xdr:twoCellAnchor>
    <xdr:from><xdr:col>13</xdr:col><xdr:row>3</xdr:row></xdr:from>
    <xdr:to><xdr:col>16</xdr:col><xdr:row>12</xdr:row></xdr:to>
    <xdr:sp>
      <xdr:nvSpPr><xdr:cNvPr id="2" name="State_ON"/></xdr:nvSpPr>
      <xdr:spPr><a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom></xdr:spPr>
      <xdr:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>ON</a:t></a:r></a:p></xdr:txBody>
    </xdr:sp>
    <xdr:clientData/>
  </xdr:twoCellAnchor>
  <xdr:twoCellAnchor>
    <xdr:from><xdr:col>8</xdr:col><xdr:row>2</xdr:row></xdr:from>
    <xdr:to><xdr:col>10</xdr:col><xdr:row>4</xdr:row></xdr:to>
    <xdr:sp>
      <xdr:nvSpPr><xdr:cNvPr id="3" name="Output_OFF"/></xdr:nvSpPr>
      <xdr:spPr><a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom></xdr:spPr>
      <xdr:txBody>
        <a:bodyPr/><a:lstStyle/>
        <a:p><a:r><a:t>OFF STS = 1</a:t></a:r></a:p>
        <a:p><a:r><a:t>Relay_1 = ON</a:t></a:r></a:p>
      </xdr:txBody>
    </xdr:sp>
    <xdr:clientData/>
  </xdr:twoCellAnchor>
  <xdr:twoCellAnchor>
    <xdr:from><xdr:col>11</xdr:col><xdr:row>4</xdr:row></xdr:from>
    <xdr:to><xdr:col>13</xdr:col><xdr:row>5</xdr:row></xdr:to>
    <xdr:sp>
      <xdr:nvSpPr><xdr:cNvPr id="4" name="Transition_Label"/></xdr:nvSpPr>
      <xdr:spPr><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr>
      <xdr:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>Transition failed</a:t></a:r></a:p></xdr:txBody>
    </xdr:sp>
    <xdr:clientData/>
  </xdr:twoCellAnchor>
  <xdr:twoCellAnchor>
    <xdr:from><xdr:col>10</xdr:col><xdr:row>4</xdr:row></xdr:from>
    <xdr:to><xdr:col>14</xdr:col><xdr:row>5</xdr:row></xdr:to>
    <xdr:cxnSp>
      <xdr:nvCxnSpPr><xdr:cNvPr id="5" name="Connector_1"/></xdr:nvCxnSpPr>
      <xdr:spPr><a:prstGeom prst="line"><a:avLst/></a:prstGeom></xdr:spPr>
    </xdr:cxnSp>
    <xdr:clientData/>
  </xdr:twoCellAnchor>
</xdr:wsDr>
"""

SHEET_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/>
</Relationships>
"""


def test_extract_excel_workbook_reads_excel_drawing_states_and_transition(tmp_path) -> None:
    path = tmp_path / "excel_drawing.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = "placeholder"
    wb.save(path)

    with zipfile.ZipFile(path, "a") as zf:
        zf.writestr("xl/worksheets/_rels/sheet1.xml.rels", SHEET_RELS)
        zf.writestr("xl/drawings/drawing1.xml", DRAWING_XML)

    parsed = extract_excel_workbook(path, [])

    assert parsed["diagram_meta"]
    joined = "\n".join(row.get("ocr_text", "") for row in parsed["diagram_meta"])
    assert "OFF" in joined
    assert "ON" in joined
    assert "Relay_1 = ON" in joined
    assert parsed["transition_candidates"]
    transition = next(row for row in parsed["transition_candidates"] if row.get("derivation") == "excel_drawing_connector")
    assert transition["from_state"] == "OFF"
    assert transition["to_state"] == "ON"
    assert transition["event"] == "Transition failed"
    assert parsed["state_rules"]
