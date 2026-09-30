r"""Read a develop XMP: envelope check, sliders, curves, masks — no deps.

Works on both forms:
  sidecar  — starts with <?xpacket?> envelope (what Camera Raw reads)
  bare     — starts directly at <x:xmpmeta> (the settings\\ store form;
             the toolkit's wrap() adds the envelope to make a sidecar)

Usage:  python scripts/xmp_reader.py <file.xmp> [--sliders]
"""
import sys, re
import xml.etree.ElementTree as ET

CRS = "http://ns.adobe.com/camera-raw-settings/1.0/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

def main():
    path = sys.argv[1]
    show_all = "--sliders" in sys.argv
    raw = open(path, "rb").read()

    enveloped = raw.lstrip()[:9] == b"<?xpacket"
    if not enveloped:
        i, j = raw.find(b"<x:xmpmeta"), raw.rfind(b"</x:xmpmeta>")
        assert i != -1 and j != -1, "not an XMP"
        raw = (b'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
               + raw[i:j + 12] + b'<?xpacket end="w"?>')

    root = ET.fromstring(raw)
    desc = root.find(f".//{{{RDF}}}Description")
    attrs = {k.split('}')[-1]: v for k, v in desc.attrib.items()
             if k.startswith("{" + CRS)}

    print(f"{path}")
    print(f"  envelope : {'<?xpacket?> sidecar' if enveloped else 'BARE (settings\\\\ form — wrap() needed for ACR)'}")
    print(f"  sliders  : {len(attrs)} crs attributes")
    for k in ("ProcessVersion", "WhiteBalance", "Temperature", "Tint",
              "Exposure2012", "Contrast2012", "Vibrance", "Saturation",
              "CropAngle", "CameraProfile"):
        if k in attrs:
            print(f"    crs:{k:16s} = {attrs[k]}")
    if show_all:
        for k in sorted(attrs):
            print(f"    crs:{k} = {attrs[k][:60]}")

    seqs = root.findall(f".//{{{RDF}}}Seq")
    print(f"  arrays   : {len(seqs)} rdf:Seq (curves, point lists)")

    masks = [d for d in root.findall(f".//{{{RDF}}}Description")
             if d.get(f"{{{CRS}}}What") == "Correction"]
    print(f"  masks    : {len(masks)} correction groups")
    for m in masks:
        nm = m.get(f"{{{CRS}}}CorrectionName", "?")
        sub = root.findall(f".//{{{RDF}}}Description")  # nested mask entries
        print(f"    - {nm}")

if __name__ == "__main__":
    main()
