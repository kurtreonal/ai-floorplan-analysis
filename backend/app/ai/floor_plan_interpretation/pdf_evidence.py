"""Bounded PDF primitives, not wall/device classifications or CAD layers.

PDFium supplies resolved drawing state. Coordinates are recovered from its
device-to-page transform, the same engine as the immutable reference raster.
Keep clip paths and Bezier controls; do not turn their bounding boxes into ink.
"""
from ctypes import c_float, c_int, c_uint
from hashlib import sha256
import json
import math
from pathlib import Path

import pypdfium2 as pdfium
from pypdfium2 import raw

VERSION = 'pdf-source-evidence-v1'
MAX_OBJECTS = 100_000
MAX_SEGMENTS = 600_000
MAX_PATH_SEGMENTS = 8192
MAX_TEXT_CHARS = 100_000
MAX_BYTES = 96 * 1024 * 1024


class PdfEvidenceError(ValueError):
    """Public callers must expose the code, not underlying parser errors."""


def _number(value):
    value = float(value)
    if not math.isfinite(value):
        raise PdfEvidenceError('PDF_EVIDENCE_INVALID_NUMBER')
    return round(value, 7)


def page_to_source(page, width, height):
    """Exact continuous inverse of PDFium's device mapping (no point rounding)."""
    if (type(width) is not int or type(height) is not int
            or min(width, height) <= 0 or max(width, height) > 4096):
        raise PdfEvidenceError('PDF_EVIDENCE_INVALID_PLANE')
    converter = pdfium.PdfPosConv(page, (0, 0, width, height, 0))
    origin = converter.to_page(0, 0)
    across = converter.to_page(width, 0)
    down = converter.to_page(0, height)
    to_page = pdfium.PdfMatrix(
        (across[0]-origin[0])/width, (across[1]-origin[1])/width,
        (down[0]-origin[0])/height, (down[1]-origin[1])/height, *origin)
    a,b,c,d,e,f = to_page.get()
    det = a*d-b*c
    if abs(det) < 1e-12:
        raise PdfEvidenceError('PDF_EVIDENCE_INVALID_TRANSFORM')
    return pdfium.PdfMatrix(d/det,-b/det,-c/det,a/det,
                           (c*f-d*e)/det,(b*e-a*f)/det)


def _color(obj, getter):
    channels = [c_uint() for _ in range(4)]
    return [v.value for v in channels] if getter(obj, *channels) else None


def _scalar(obj, getter):
    value = c_float()
    return _number(value.value) if getter(obj, value) else None


def _commands(count, getter, matrix):
    if not 0 <= count <= MAX_PATH_SEGMENTS:
        raise PdfEvidenceError('PDF_EVIDENCE_PATH_BUDGET')
    result = []
    for i in range(count):
        segment = getter(i)
        x,y = c_float(),c_float()
        if not segment or not raw.FPDFPathSegment_GetPoint(segment,x,y):
            raise PdfEvidenceError('PDF_EVIDENCE_INVALID_PATH')
        result.append([raw.FPDFPathSegment_GetType(segment),
                       *map(_number,matrix.on_point(x.value,y.value)),
                       bool(raw.FPDFPathSegment_GetClose(segment))])
    return result


def _clip(obj):
    """Retain PDFium's native clip coordinates and container, not guessed polygons."""
    clip = raw.FPDFPageObj_GetClipPath(obj)
    if not clip:
        return []
    count = raw.FPDFClipPath_CountPaths(clip)
    # PDFium returns -1 for an object with no clipping-path data.
    if count == -1:
        return []
    if not 0 <= count <= 64:
        raise PdfEvidenceError('PDF_EVIDENCE_CLIP_BUDGET')
    return [_commands(raw.FPDFClipPath_CountPathSegments(clip,i),
                      lambda j: raw.FPDFClipPath_GetPathSegment(clip,i,j),
                      pdfium.PdfMatrix()) for i in range(count)]


def extract_pdf_evidence(source_path, *, page_number, width, height):
    """Read-only, bounded extraction; never modify/render an uploaded original."""
    source = Path(source_path)
    if (type(page_number) is not int or page_number <= 0
            or source.suffix.lower() != '.pdf' or not source.is_file()
            or source.stat().st_size > MAX_BYTES):
        raise PdfEvidenceError('PDF_EVIDENCE_INVALID_SOURCE')
    digest = sha256(source.read_bytes()).hexdigest()
    try:
        with pdfium.PdfDocument(str(source)) as document:
            if page_number > len(document):
                raise PdfEvidenceError('PDF_EVIDENCE_PAGE_OUT_OF_RANGE')
            page = document[page_number-1]
            textpage = page.get_textpage()
            try:
                mapping = page_to_source(page,width,height)
                objects, paths, texts, images = [], [], [], []
                segments = chars = 0
                form_ids = {}
                for index,obj in enumerate(page.get_objects(textpage=textpage),1):
                    if index > MAX_OBJECTS:
                        raise PdfEvidenceError('PDF_EVIDENCE_OBJECT_BUDGET')
                    if obj.type==raw.FPDF_PAGEOBJ_FORM and obj.level>=14:
                        raise PdfEvidenceError('PDF_EVIDENCE_FORM_DEPTH_BUDGET')
                    own = obj.get_matrix()
                    transform = own
                    parent = obj.container
                    while parent is not None:
                        transform = transform.multiply(parent.get_matrix())
                        parent = parent.container
                    native_bounds = obj.get_bounds()
                    # PDFium object bounds include its own transform, not ancestors.
                    ancestors = pdfium.PdfMatrix()
                    parent = obj.container
                    while parent is not None:
                        ancestors = ancestors.multiply(parent.get_matrix())
                        parent = parent.container
                    corners = [mapping.on_point(*ancestors.on_point(x,y))
                               for x in (native_bounds[0],native_bounds[2])
                               for y in (native_bounds[1],native_bounds[3])]
                    bbox = [_number(min(p[0] for p in corners)),_number(min(p[1] for p in corners)),
                            _number(max(p[0] for p in corners)),_number(max(p[1] for p in corners))]
                    record = dict(id=index,type=obj.type,bounds=bbox,level=obj.level,
                        parent_id=form_ids.get(obj.level-1),
                        transform=list(map(_number,transform.get())),
                        own_transform=list(map(_number,own.get())),
                        clip_paths=_clip(obj),clip_coordinate_system='pdfium_object_container')
                    segments += sum(len(path) for path in record['clip_paths'])
                    if obj.type == raw.FPDF_PAGEOBJ_PATH:
                        commands = _commands(raw.FPDFPath_CountSegments(obj),
                            lambda i: raw.FPDFPath_GetPathSegment(obj,i),transform.multiply(mapping))
                        segments += len(commands)
                        count = raw.FPDFPageObj_GetDashCount(obj)
                        if not 0 <= count <= 64:
                            raise PdfEvidenceError('PDF_EVIDENCE_DASH_BUDGET')
                        dashes = (c_float * count)()
                        if count and not raw.FPDFPageObj_GetDashArray(obj,dashes,count):
                            raise PdfEvidenceError('PDF_EVIDENCE_INVALID_DASH')
                        fill,stroke = c_int(),c_int()
                        if not raw.FPDFPath_GetDrawMode(obj,fill,stroke):
                            raise PdfEvidenceError('PDF_EVIDENCE_INVALID_STYLE')
                        record.update(commands=commands,stroke=bool(stroke.value),fill_mode=fill.value,
                            stroke_width=_scalar(obj,raw.FPDFPageObj_GetStrokeWidth),
                            stroke_color=_color(obj,raw.FPDFPageObj_GetStrokeColor),
                            fill_color=_color(obj,raw.FPDFPageObj_GetFillColor),
                            dash_array=list(map(_number,dashes)),
                            dash_phase=_scalar(obj,raw.FPDFPageObj_GetDashPhase),
                            line_cap=raw.FPDFPageObj_GetLineCap(obj),line_join=raw.FPDFPageObj_GetLineJoin(obj))
                        paths.append(record)
                    elif obj.type == raw.FPDF_PAGEOBJ_TEXT:
                        text = obj.extract()
                        chars += len(text)
                        if chars > MAX_TEXT_CHARS:
                            raise PdfEvidenceError('PDF_EVIDENCE_TEXT_BUDGET')
                        record['text'] = text
                        texts.append(record)
                    elif obj.type == raw.FPDF_PAGEOBJ_IMAGE:
                        images.append(record)
                    objects.append(record)
                    if obj.type == raw.FPDF_PAGEOBJ_FORM:
                        form_ids[obj.level] = index
                    if segments > MAX_SEGMENTS:
                        raise PdfEvidenceError('PDF_EVIDENCE_SEGMENT_BUDGET')
                result = dict(version=VERSION,source_sha256=digest,page_number=page_number,
                    parser_runtime=dict(binding=str(pdfium.PYPDFIUM_INFO),renderer=str(pdfium.PDFIUM_INFO)),
                    source_plane=dict(width_pixels=width,height_pixels=height),
                    rotation=page.get_rotation(),crop_box=list(page.get_cropbox()),
                    pdf_to_source=list(map(_number,mapping.get())),
                    capability='vector_and_raster' if paths else 'raster',
                    objects=objects,object_counts=dict(total=len(objects),paths=len(paths),
                        texts=len(texts),images=len(images),segments=segments),
                    semantic_layers_available=False,physical_thickness_available=False)
                # Hash every preserved primitive and style for immutable run provenance.
                encoded = json.dumps(result,sort_keys=True,separators=(',',':')).encode()
                if len(encoded) > MAX_BYTES:
                    raise PdfEvidenceError('PDF_EVIDENCE_BYTE_BUDGET')
                result['evidence_sha256'] = sha256(encoded).hexdigest()
                return result
            finally:
                textpage.close()
                page.close()
    except PdfEvidenceError:
        raise
    except Exception:
        raise PdfEvidenceError('PDF_EVIDENCE_EXTRACTION_FAILED') from None


class PrimitiveIndex:
    """Bounded uniform-grid lookup, no all-pairs comparison of PDF paths."""
    def __init__(self, evidence, cell_size=128):
        self.objects = evidence['objects']
        self.cell_size = cell_size
        self.cells = {}
        self.broad = []
        for i,item in enumerate(self.objects):
            keys = self._keys(item['bounds'])
            if len(keys) > 256:
                self.broad.append(i)
            else:
                for key in keys:
                    self.cells.setdefault(key,[]).append(i)

    def _keys(self, bounds):
        a,b,c,d = [math.floor(v/self.cell_size) for v in bounds]
        if (c-a+1)*(d-b+1) > 256:
            return range(257)
        return [(x,y) for x in range(a,c+1) for y in range(b,d+1)]

    def query(self, bounds):
        keys = self._keys(bounds)
        indices = (range(len(self.objects)) if len(keys)>256 else
                   sorted(set(self.broad).union(*(self.cells.get(k,[]) for k in keys))))
        a,b,c,d = bounds
        return [self.objects[i] for i in indices if self.objects[i]['bounds'][0]<=c
            and self.objects[i]['bounds'][2]>=a and self.objects[i]['bounds'][1]<=d
            and self.objects[i]['bounds'][3]>=b]
