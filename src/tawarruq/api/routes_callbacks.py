from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from tawarruq.database import get_db
from tawarruq.services.callback_service import (
    handle_mno_possession_callback,
    handle_mpesa_b2c_result,
    handle_mpesa_stk_callback,
)

router = APIRouter()


@router.post(
    "/kenya/callbacks/mpesa/b2c/result",
    tags=["Kenya Callbacks"],
    summary="Daraja B2C ResultURL (M-Pesa disbursement confirmation)",
    include_in_schema=True,
)
async def mpesa_b2c_result(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    body = await request.json()
    result = handle_mpesa_b2c_result(db, body)
    db.commit()
    return {"ResultCode": 0, "ResultDesc": "Accepted", **result}


@router.post(
    "/kenya/callbacks/mpesa/b2c/timeout",
    tags=["Kenya Callbacks"],
    summary="Daraja B2C QueueTimeOutURL",
)
async def mpesa_b2c_timeout(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    body = await request.json()
    result = handle_mpesa_b2c_result(db, body)
    db.commit()
    return {"ResultCode": 0, "ResultDesc": "Accepted", **result}


@router.post(
    "/kenya/callbacks/mpesa/stk",
    tags=["Kenya Callbacks"],
    summary="Daraja STK Push CallBackURL (repayment collection)",
)
async def mpesa_stk_callback(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    body = await request.json()
    result = handle_mpesa_stk_callback(db, body)
    db.commit()
    return result


@router.post(
    "/kenya/callbacks/mno/possession",
    tags=["Kenya Callbacks"],
    summary="MNO partner constructive possession webhook",
)
async def mno_possession_callback(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    body = await request.json()
    result = handle_mno_possession_callback(db, body)
    db.commit()
    return result
