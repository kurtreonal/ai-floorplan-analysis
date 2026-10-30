"""Bounded official-PH source discovery, not training or a rights grant.

Original public PDFs are immutable inspection archives. Only explicitly
selected electrical pages may later enter the <=50-page preparation workflow.
No remote content is executed, no private drawings leave the computer.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import ssl
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from pypdf import PdfReader

MAX_BYTES = 25 * 1024 * 1024
MAX_INSPECTION_PAGES = 250  # Archive inspection only; intake limit stays 50.
SOURCES = (
    ('dpwh-pangascasan', 'https://www.dpwh.gov.ph/dpwh/sites/default/files/webform/civil_works/advertisement/25a00275_plans_optimize_part5.pdf'),
    ('dpwh-bucal', 'https://dpwh.gov.ph/dpwh/sites/default/files/webform/civil_works/bid_bulletin/23de0009_bulletin_plans_17.pdf'),
    ('tesda-ncr', 'https://www.tesda.gov.ph/Uploads/File/PhilGeps/2021/Bid%20Docs%20-%20RTC%20-%20NCR%20Part%202.pdf'),
    ('slsu', 'https://southernleytestateu.edu.ph/attachments/article/728/merged.pdf'),
    ('bsu', 'https://bsu.edu.ph/wp-content/uploads/IB2024/IB-2024-22A-bid-docs_whole.pdf'),
    ('up-visayas', 'https://www.upv.edu.ph/files/itb-2024-008.pdf'),
    ('ppsc-pagadian', 'https://ppsc.gov.ph/wp-content/uploads/2025/02/NPC_Pagadian_Phase1_Electrical-Plans.pdf'),
    ('mwss', 'https://mwss.gov.ph/wp-content/uploads/ANNEX-1-of-TOR-MWSS-MLP-2-2023_redacted_opt.pdf'),
    ('qc-masambong-school', 'https://quezoncity.gov.ph/wp-content/uploads/2025/02/25-00004.pdf'),
    ('bir-office', 'https://bir-cdn.bir.gov.ph/BIR/pdf/RR9B%20-%20Detailed%20Drawings.pdf'),
    ('nfa-dumangas', 'https://nfaweb.nfa.gov.ph/webapp/bac/ebps.nsf/wAll/83D06255520A05D348258DA20049C814/%24File/Infra2ndPostingAfterCancellation.pdf?OpenElement='),
    ('dpwh-health-tent', 'https://www.dpwh.gov.ph/dpwh/sites/default/files/references/standard_design/4.%20DPWH%20Modified%20Standard%20Two%20%282%29%20Units%20Health%20Facility%20Tent%20%28with%20isolation%20cubicle%29.pdf'),
)


def official_url(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ''
    return (parsed.scheme == 'https' and not parsed.username and not parsed.password
            and parsed.port in (None, 443)
            and host.endswith(('.gov.ph', '.edu.ph')))


def bounded_pdf(stream):
    content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError('source_byte_bound_exceeded')
    if not content.startswith(b'%PDF-'):
        raise ValueError('not_a_pdf_or_access_blocked')
    reader = PdfReader(BytesIO(content))
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_INSPECTION_PAGES:
        raise ValueError('encrypted_or_inspection_page_bound_exceeded')
    return content, reader


def inspect_pages(reader):
    rows = []
    patterns = {
        'lighting': r'(?:lighting|illumination)\s+(?:lay[\s-]*out|plan)',
        'power': r'power\s+(?:lay[\s-]*out|plan)',
        'security': r'(?:cctv|security|surveillance|fire\s+alarm|data\s+network|telephone)\s+(?:system\s+)?(?:lay[\s-]*out|plan)',
        'legend': r'legend(?:s)?(?:\s*(?:and|&)\s*symbols)?',
    }
    for number, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or '')[:100_000]
        flat = re.sub(r'\s+', ' ', text)
        matches = {kind: [m.group() for m in re.finditer(pattern, flat, re.I)][:8]
                   for kind, pattern in patterns.items()}
        types = [kind for kind, values in matches.items() if values]
        if types:
            rows.append({'page_number': number, 'proposed_sheet_types': types,
                         'text_evidence': matches, 'selection_state': 'assistant_proposal_not_visual_review',
                         'pec_note_present': bool(re.search(r'Philippine\s+Electrical\s+Code', flat, re.I)),
                         'training_eligible': False})
    return rows


def collect(output, sources=SOURCES):
    output = Path(output)
    if output.exists():
        raise FileExistsError('Discovery revisions are immutable')
    output.mkdir(parents=True)
    records = []
    for identity, url in sources:
        record = {'source_id': identity, 'source_url': url,
                  'rights_status': 'unverified_training_excluded',
                  'pec_compliance': 'not_certified_by_this_inspection',
                  'training_eligible': False, 'split': 'unassigned',
                  'project_relationships': 'unverified_keep_pages_together'}
        try:
            if not re.fullmatch(r'[a-z0-9-]{1,60}', identity) or not official_url(url):
                raise ValueError('invalid_official_source')
            with urlopen(Request(url, headers={'User-Agent': 'VED-local-dataset-research/1.0'}),
                         timeout=20, context=ssl.create_default_context()) as response:
                if not official_url(response.url):
                    raise ValueError('redirect_outside_official_hosts')
                content, reader = bounded_pdf(response)
                record['resolved_url'] = response.url
            folder = output / identity
            folder.mkdir()
            with (folder / 'original.pdf').open('xb') as stream:
                stream.write(content)
            record.update(status='downloaded_for_inspection', sha256=sha256(content).hexdigest(),
                          bytes=len(content), page_count=len(reader.pages),
                          proposed_pages=inspect_pages(reader))
            with (folder / 'inventory.json').open('x', encoding='utf-8') as stream:
                json.dump(record, stream, indent=2)
        except Exception as error:
            # No credentials, exception URLs or remote response bodies in logs.
            record['status'] = 'unavailable'
            record['failure_kind'] = type(error).__name__
        records.append(record)
        print(identity, record['status'], record.get('page_count', ''), flush=True)
    manifest = {'schema': 'ved-ph-public-electrical-discovery-v1',
                'created_utc': datetime.now(timezone.utc).isoformat(),
                'source_count': len(records), 'sources': records,
                'notice': 'Public access and PEC notes are not training rights or compliance certification.'}
    with (output / 'manifest.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    collect(parser.parse_args().output)
