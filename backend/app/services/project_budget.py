"""Allocated PHP budget in existing intake JSON; estimates remain immutable."""
from decimal import Decimal
from app.models.client_workflow import ProjectAssignment
from app.services.intake_schema import details


def allocated(db,project_id):
    value=details(db,db.get(ProjectAssignment,project_id),'intake_details').get('allocated_budget')
    return Decimal(str(value)).quantize(Decimal('.01')) if value is not None else None


def comparison(db,project_id,totals,*,incomplete=False):
    budget=allocated(db,project_id)
    if budget is None:return None
    total=totals.get('PHP')
    if total is None:return dict(allocated_budget=str(budget),currency='PHP',estimated_total=None,status='currency_mismatch' if totals else 'awaiting_estimate')
    total=Decimal(str(total)).quantize(Decimal('.01'))
    difference=budget-total
    partial=incomplete or any(currency!='PHP' for currency in totals)
    return dict(allocated_budget=str(budget),currency='PHP',estimated_total=str(total),remaining=str(max(Decimal(0),difference)),
        over_budget=str(max(Decimal(0),-difference)),status='over_budget' if difference<0 else 'within_budget',incomplete=partial)
