from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class ExperimentRun(Base):
    __tablename__ = "experiment_runs"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(120), default="Healthcare Information Assistant")
    prompt_type = Column(String(50), nullable=False)
    prompt_text = Column(Text, nullable=False)
    input_text = Column(Text, nullable=False)
    output_mode = Column(String(20), nullable=False)  # text | json
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    outputs = relationship("ModelOutput", back_populates="run", cascade="all, delete-orphan")


class ModelOutput(Base):
    __tablename__ = "model_outputs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("experiment_runs.id"), nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    model_symbol = Column(String(10), nullable=False)
    provider_name = Column(String(100), nullable=False)
    raw_response = Column(Text, nullable=False)
    parsed_json = Column(Text, nullable=True)
    is_json_valid = Column(Boolean, default=False)
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("ExperimentRun", back_populates="outputs")
    evaluation = relationship("OutputEvaluation", back_populates="output", uselist=False, cascade="all, delete-orphan")


class OutputEvaluation(Base):
    __tablename__ = "output_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    output_id = Column(Integer, ForeignKey("model_outputs.id"), nullable=False, unique=True)
    accuracy = Column(Integer, nullable=False)
    clarity = Column(Integer, nullable=False)
    relevance = Column(Integer, nullable=False)
    failure_tags = Column(String(300), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    output = relationship("ModelOutput", back_populates="evaluation")
