"""Harmless export metadata tolerance; structural corruption stays rejected."""
from hashlib import sha256
import pytest
from app.services.upload_validation import validate_floor_plan_upload,UploadValidationError


def document(catalog):
    objects=[catalog,b'<< /Type /Pages /Count 1 /Kids [3 0 R] >>',
             b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] >>']
    data=b'%PDF-1.7\n';offsets=[]
    for i,obj in enumerate(objects,1):
        offsets.append(len(data));data+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    start=len(data)
    data+=b'xref\n0 4\n0000000000 65535 f \n'
    data+=b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets)
    return data+b'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n'+str(start).encode()+b'\n%%EOF\n'


@pytest.mark.parametrize('key,first,last',[(b'PageMode',b'UseOC',b'UseOutlines'),
                                         (b'PageLayout',b'SinglePage',b'TwoColumnLeft')])
def test_duplicate_non_geometric_preferences_do_not_reject_valid_pages_or_change_bytes(key,first,last):
    data=document(b'<< /Type /Catalog /Pages 2 0 R /'+key+b' /'+first+b' /'+key+b' /'+last+b' >>')
    digest=sha256(data).hexdigest()
    result=validate_floor_plan_upload(filename='new-export.pdf',declared_mime_type='application/pdf',
        content=data,max_file_size_bytes=100_000)
    assert result.page_count==1 and result.file_size==len(data)
    assert sha256(data).hexdigest()==digest


def test_duplicate_structural_keys_are_not_recovered_even_after_viewer_metadata_recovery():
    data=document(b'<< /Type /Catalog /PageMode /UseOC /PageMode /UseOutlines /Pages 2 0 R /Pages 2 0 R >>')
    with pytest.raises(UploadValidationError) as error:
        validate_floor_plan_upload(filename='ambiguous.pdf',declared_mime_type='application/pdf',content=data,
                                   max_file_size_bytes=100_000)
    assert error.value.code=='UPLOAD_PDF_CORRUPT'
