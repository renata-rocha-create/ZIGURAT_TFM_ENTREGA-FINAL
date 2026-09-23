"""
bcf_export.py — Exporta as não conformidades em BCF 2.1 (.bcfzip).

BCF (BIM Collaboration Format, buildingSMART) é o "post-it digital" do BIM:
cada tópico traz título, descrição, o GlobalId do elemento e uma câmera
apontada para ele. Abre no BIMcollab Zoom (gratuito), Solibri, Navisworks
e no Revit (via plugin).

Um .bcfzip é só um ZIP com esta estrutura:
    bcf.version
    <guid-do-topico>/markup.bcf        → título, descrição, status, autor
    <guid-do-topico>/viewpoint.bcfv    → elemento selecionado + câmera
"""
import io
import uuid
import zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape

import numpy as np

AUTOR = "Auditor NBR 9050 (TFM Zigurat)"


def _versao():
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Version VersionId="2.1"><DetailedVersion>2.1</DetailedVersion></Version>')


def _markup(topic_guid, vp_guid, arquivo_ifc, titulo, descricao, labels, data):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Markup>
  <Header>
    <File isExternal="true">
      <Filename>{escape(arquivo_ifc)}</Filename>
      <Date>{data}</Date>
    </File>
  </Header>
  <Topic Guid="{topic_guid}" TopicType="Issue" TopicStatus="Open">
    <Title>{escape(titulo)}</Title>
    <Priority>Normal</Priority>
    {''.join(f"<Labels>{escape(l)}</Labels>" for l in labels)}
    <CreationDate>{data}</CreationDate>
    <CreationAuthor>{escape(AUTOR)}</CreationAuthor>
    <Description>{escape(descricao)}</Description>
  </Topic>
  <Viewpoints Guid="{vp_guid}">
    <Viewpoint>viewpoint.bcfv</Viewpoint>
  </Viewpoints>
</Markup>'''


def _xyz(tag, v):
    return (f"<{tag}><X>{v[0]:.4f}</X><Y>{v[1]:.4f}</Y><Z>{v[2]:.4f}</Z></{tag}>")


def _camera(bbox_min, bbox_max):
    """Câmera em perspectiva olhando o centro do elemento, a uma distância
    proporcional ao tamanho dele (como um 'zoom to fit' do Navisworks)."""
    bmin, bmax = np.array(bbox_min), np.array(bbox_max)
    centro = (bmin + bmax) / 2
    tamanho = max(float(np.linalg.norm(bmax - bmin)), 1.0)
    pos = centro + np.array([-1.0, -1.0, 0.7]) * tamanho * 1.6
    direcao = centro - pos
    direcao = direcao / np.linalg.norm(direcao)
    return ("<PerspectiveCamera>"
            + _xyz("CameraViewPoint", pos) + _xyz("CameraDirection", direcao)
            + _xyz("CameraUpVector", (0.0, 0.0, 1.0))
            + "<FieldOfView>60</FieldOfView></PerspectiveCamera>")


def _viewpoint(vp_guid, global_id, bbox):
    cam = _camera(*bbox) if bbox else ""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<VisualizationInfo Guid="{vp_guid}">
  <Components>
    <Selection>
      <Component IfcGuid="{escape(global_id)}"/>
    </Selection>
    <Visibility DefaultVisibility="true"/>
    <Coloring>
      <Color Color="FFE03C3C">
        <Component IfcGuid="{escape(global_id)}"/>
      </Color>
    </Coloring>
  </Components>
  {cam}
</VisualizationInfo>'''


def gerar_bcfzip(linhas: list[dict], arquivo_ifc: str, malhas: dict | None = None,
                 status_incluidos=("Não Conforme",)) -> tuple[bytes, int]:
    """
    Gera o .bcfzip com um tópico por verificação não conforme.
    Devolve (bytes do arquivo, nº de tópicos).
    """
    bboxes = {}
    for a in (malhas or {}).get("auditados", []):
        bboxes[a["global_id"]] = (a["bbox_min"], a["bbox_max"])

    data = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    buf = io.BytesIO()
    n = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("bcf.version", _versao())
        for l in linhas or []:
            if l["status"] not in status_incluidos:
                continue
            topic, vp = str(uuid.uuid4()), str(uuid.uuid4())
            titulo = f"NBR 9050 {l['item_nbr']} · {l['categoria']} · {l['status']}"
            descricao = (
                f"Elemento: {l['nome']}\n"
                f"Pavimento: {l['pavimento']}\n"
                f"Medido: {l['valor_medido']}\n"
                f"Exigido: {l['valor_exigido']}\n"
                f"Confiança do dado: {l['confianca']} ({l['fonte_dado']})\n"
                + (f"Observação: {l['mensagem']}\n" if l.get("mensagem") else "")
                + f"GlobalId: {l['global_id']}"
            )
            labels = ["NBR 9050", f"Item {l['item_nbr']}", l["categoria"]]
            z.writestr(f"{topic}/markup.bcf",
                       _markup(topic, vp, arquivo_ifc, titulo, descricao, labels, data))
            z.writestr(f"{topic}/viewpoint.bcfv",
                       _viewpoint(vp, l["global_id"], bboxes.get(l["global_id"])))
            n += 1
    return buf.getvalue(), n
