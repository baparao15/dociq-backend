from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import Optional, List
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from models import User, Document, Analysis
from database import get_db, create_tables
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from document_processor import DocumentProcessor
from risk_analyzer import RiskAnalyzer
from rewrite_engine import RewriteEngine
from summary_engine import SummaryEngine

app = FastAPI(title="Legal Document Demystifier API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

create_tables()

# Create demo user if it doesn't exist

document_processor = DocumentProcessor()
risk_analyzer = RiskAnalyzer()
rewrite_engine = RewriteEngine()
summary_engine = SummaryEngine()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Ensure uploads directory exists
if not UPLOAD_DIR.exists():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Created upload directory: {UPLOAD_DIR.absolute()}")

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

class DocumentUpdateRequest(BaseModel):
    edited_text: str

@app.get("/")
async def root():
    return {"message": "Legal Document Demystifier API", "status": "running"}

@app.get("/health")
async def health():
    gemini_status = "configured" if os.getenv("GEMINI_API_KEY") else "not configured"
    return {
        "status": "healthy",
        "gemini": gemini_status,
        "database": "connected"
    }

@app.post("/api/auth/signup", response_model=TokenResponse)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user = User(
        email=request.email,
        hashed_password=get_password_hash(request.password),
        full_name=request.full_name
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name
        }
    }

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name
        }
    }

@app.get("/api/auth/me")
async def get_me(current_user: User = Depends(get_current_active_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name
    }

@app.post("/api/analyze-document")
async def analyze_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    file_path = None
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Check file size (10MB limit)
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB")
        
        # Check file type
        allowed_types = ['.pdf', '.docx', '.txt']
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_types:
            raise HTTPException(status_code=422, detail=f"Unsupported file type. Allowed types: {', '.join(allowed_types)}")
        
        print(f"Processing file: {file.filename}, Size: {len(content)} bytes, Type: {file_ext}")
        
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as f:
            f.write(content)
        
        text = document_processor.extract_text(str(file_path))
        
        if file_path.exists():
            os.remove(file_path)
        
        risks = risk_analyzer.analyze(text)
        
        summary = summary_engine.generate_summary(text)
        
        rewrites = None
        if risks:
            try:
                rewrites = rewrite_engine.rewrite_clauses([r["clause"] for r in risks])
                if rewrites:
                    for i, risk in enumerate(risks):
                        if i < len(rewrites):
                            risk["suggested_rewrite"] = rewrites[i]
            except Exception as e:
                print(f"Rewrite error: {e}")
        
        document = Document(
            user_id=current_user.id,
            filename=file.filename,
            original_text=text
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        analysis = Analysis(
            document_id=document.id,
            summary=summary,
            risks=risks,
            rewrites=rewrites
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        
        return {
            "analysis_id": analysis.id,
            "document_name": file.filename,
            "text_length": len(text),
            "risks_found": len(risks),
            "risks": risks,
            "original_text": text
        }
    
    except Exception as e:
        if file_path and file_path.exists():
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze-text")
async def analyze_text(
    text: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    try:
        risks = risk_analyzer.analyze(text)
        
        summary = summary_engine.generate_summary(text)
        
        rewrites = None
        if risks:
            try:
                rewrites = rewrite_engine.rewrite_clauses([r["clause"] for r in risks])
                if rewrites:
                    for i, risk in enumerate(risks):
                        if i < len(rewrites):
                            risk["suggested_rewrite"] = rewrites[i]
            except Exception as e:
                print(f"Rewrite error: {e}")
        
        document = Document(
            user_id=current_user.id,
            filename="Text Input",
            original_text=text
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        analysis = Analysis(
            document_id=document.id,
            summary=summary,
            risks=risks,
            rewrites=rewrites
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        
        return {
            "analysis_id": analysis.id,
            "document_name": "Text Input",
            "text_length": len(text),
            "risks_found": len(risks),
            "risks": risks,
            "original_text": text
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents")
async def get_documents(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    documents = db.query(Document).filter(
        Document.user_id == current_user.id
    ).order_by(Document.created_at.desc()).all()
    
    return [{
        "id": doc.id,
        "filename": doc.filename,
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat()
    } for doc in documents]

@app.get("/api/documents/{document_id}")
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    analysis = db.query(Analysis).filter(
        Analysis.document_id == document_id
    ).first()
    
    return {
        "id": document.id,
        "filename": document.filename,
        "original_text": document.original_text,
        "edited_text": document.edited_text,
        "created_at": document.created_at.isoformat(),
        "summary": analysis.summary if analysis else None,
        "risks": analysis.risks if analysis else [],
        "rewrites": analysis.rewrites if analysis else None
    }

@app.put("/api/documents/{document_id}")
async def update_document(
    document_id: int,
    request: DocumentUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    document.edited_text = request.edited_text
    db.commit()
    
    return {"success": True, "message": "Document updated successfully"}

# Demo endpoints without authentication for testing
@app.post("/api/demo/analyze-document")
async def demo_analyze_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    file_path = None
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Check file size (10MB limit)
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB")
        
        # Check file type
        allowed_types = ['.pdf', '.docx', '.txt']
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_types:
            raise HTTPException(status_code=422, detail=f"Unsupported file type. Allowed types: {', '.join(allowed_types)}")
        
        print(f"Processing demo file: {file.filename}, Size: {len(content)} bytes, Type: {file_ext}")
        
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as f:
            f.write(content)
        
        text = document_processor.extract_text(str(file_path))
        
        if file_path.exists():
            os.remove(file_path)
        
        risks = risk_analyzer.analyze(text)
        
        summary = summary_engine.generate_summary(text)
        
        rewrites = None
        if risks:
            try:
                rewrites = rewrite_engine.rewrite_clauses([r["clause"] for r in risks])
                if rewrites:
                    for i, risk in enumerate(risks):
                        if i < len(rewrites):
                            risk["suggested_rewrite"] = rewrites[i]
            except Exception as e:
                print(f"Rewrite error: {e}")
        
        return {
            "analysis_id": 0,  # Demo mode
            "document_name": file.filename,
            "text_length": len(text),
            "risks_found": len(risks),
            "risks": risks,
            "original_text": text
        }
    
    except Exception as e:
        if file_path and file_path.exists():
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/demo/analyze-text")
async def demo_analyze_text(
    text: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        risks = risk_analyzer.analyze(text)
        
        summary = summary_engine.generate_summary(text)
        
        rewrites = None
        if risks:
            try:
                rewrites = rewrite_engine.rewrite_clauses([r["clause"] for r in risks])
                if rewrites:
                    for i, risk in enumerate(risks):
                        if i < len(rewrites):
                            risk["suggested_rewrite"] = rewrites[i]
            except Exception as e:
                print(f"Rewrite error: {e}")
        
        return {
            "analysis_id": 0,  # Demo mode
            "document_name": "Text Input",
            "text_length": len(text),
            "risks_found": len(risks),
            "risks": risks,
            "original_text": text
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
