from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import json
from app.db.session import Base

class Persona(Base):
    __tablename__ = "personas"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    knowledge_sources = relationship("KnowledgeSource", back_populates="persona", cascade="all, delete-orphan")
    voice_profile = relationship("VoiceProfile", back_populates="persona", uselist=False, cascade="all, delete-orphan")
    voice_samples = relationship("VoiceSample", back_populates="persona", cascade="all, delete-orphan")

class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    persona_id = Column(String, ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, index=True)
    source_type = Column(String, index=True) # UPLOAD, WIKIPEDIA, WEBSITE
    source_url = Column(String, nullable=True)
    original_filename = Column(String, nullable=True)
    
    entity_id = Column(String, ForeignKey("entities.id", ondelete="SET NULL"), nullable=True)
    content_hash = Column(String, nullable=True)
    
    status = Column(String, default="PENDING") # PENDING, PROCESSING, COMPLETED, FAILED
    chunk_count = Column(Integer, default=0)
    source_count = Column(Integer, default=1)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    persona = relationship("Persona", back_populates="knowledge_sources")
    entity = relationship("Entity", back_populates="knowledge_sources")
    structured_records = relationship("StructuredRecord", back_populates="knowledge_source", cascade="all, delete-orphan")
    explicit_facts = relationship("ExplicitFact", back_populates="knowledge_source", cascade="all, delete-orphan")

class Entity(Base):
    __tablename__ = "entities"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    persona_id = Column(String, ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, index=True)
    aliases_json = Column(Text, default="[]") # JSON list of strings
    
    knowledge_sources = relationship("KnowledgeSource", back_populates="entity")
    datasets = relationship("DatasetSchema", back_populates="entity")
    explicit_facts = relationship("ExplicitFact", back_populates="entity")

    @property
    def aliases(self):
        return json.loads(self.aliases_json)
    
    @aliases.setter
    def aliases(self, val):
        self.aliases_json = json.dumps(val)

class DatasetSchema(Base):
    __tablename__ = "dataset_schemas"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_id = Column(String, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    dataset_type = Column(String, index=True) # e.g. "filmography", "sports_statistics"
    schema_confidence = Column(Float, default=1.0)
    
    primary_fields_json = Column(Text, default="[]")
    attributes_json = Column(Text, default="[]")
    sortable_fields_json = Column(Text, default="[]")
    filterable_fields_json = Column(Text, default="[]")

    entity = relationship("Entity", back_populates="datasets")
    records = relationship("StructuredRecord", back_populates="dataset", cascade="all, delete-orphan")

    @property
    def primary_fields(self): return json.loads(self.primary_fields_json)
    @primary_fields.setter
    def primary_fields(self, val): self.primary_fields_json = json.dumps(val)

    @property
    def attributes(self): return json.loads(self.attributes_json)
    @attributes.setter
    def attributes(self, val): self.attributes_json = json.dumps(val)

    @property
    def sortable_fields(self): return json.loads(self.sortable_fields_json)
    @sortable_fields.setter
    def sortable_fields(self, val): self.sortable_fields_json = json.dumps(val)

    @property
    def filterable_fields(self): return json.loads(self.filterable_fields_json)
    @filterable_fields.setter
    def filterable_fields(self, val): self.filterable_fields_json = json.dumps(val)

class StructuredRecord(Base):
    __tablename__ = "structured_records"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(String, ForeignKey("dataset_schemas.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(String, ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False)
    entity_id = Column(String, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    
    record_index = Column(Integer)
    original_row_number = Column(Integer)
    
    raw_data_json = Column(Text, default="{}")
    normalized_data_json = Column(Text, default="{}")
    
    dataset = relationship("DatasetSchema", back_populates="records")
    knowledge_source = relationship("KnowledgeSource", back_populates="structured_records")

    @property
    def raw_data(self): return json.loads(self.raw_data_json)
    @raw_data.setter
    def raw_data(self, val): self.raw_data_json = json.dumps(val)

    @property
    def normalized_data(self): return json.loads(self.normalized_data_json)
    @normalized_data.setter
    def normalized_data(self, val): self.normalized_data_json = json.dumps(val)

class ExplicitFact(Base):
    __tablename__ = "explicit_facts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_id = Column(String, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(String, ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False)
    
    subject = Column(String, index=True)
    predicate = Column(String, index=True)
    object_val = Column(String)
    
    year = Column(Integer, nullable=True, index=True)
    position = Column(Integer, nullable=True) # e.g. 50 (for 50th film)
    confidence = Column(Float, default=1.0)
    
    entity = relationship("Entity", back_populates="explicit_facts")
    knowledge_source = relationship("KnowledgeSource", back_populates="explicit_facts")

class VoiceProfile(Base):
    __tablename__ = "voice_profiles"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    persona_id = Column(String, ForeignKey("personas.id", ondelete="CASCADE"), nullable=False, unique=True)
    status = Column(String, default="NOT_CONFIGURED") # NOT_CONFIGURED, SAMPLES_UPLOADED, PROCESSING, READY, FAILED
    provider = Column(String, default="local")
    provider_metadata_json = Column(Text, default="{}")
    reference_audio_files_json = Column(Text, default="[]")
    voice_id = Column(String, nullable=True) # model_path, embedding_path, or external voice ID
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    persona = relationship("Persona", back_populates="voice_profile")

    @property
    def active_provider(self):
        return self.provider

    @active_provider.setter
    def active_provider(self, val):
        self.provider = val

    @property
    def provider_metadata(self):
        return json.loads(self.provider_metadata_json or "{}")

    @provider_metadata.setter
    def provider_metadata(self, val):
        self.provider_metadata_json = json.dumps(val or {})

    @property
    def reference_audio_files(self):
        return json.loads(self.reference_audio_files_json)
    
    @reference_audio_files.setter
    def reference_audio_files(self, val):
        self.reference_audio_files_json = json.dumps(val)

class VoiceSample(Base):
    __tablename__ = "voice_samples"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    persona_id = Column(String, ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    duration = Column(Float, default=0.0) # in seconds
    sample_rate = Column(Integer, default=22050)
    file_size = Column(Integer, default=0) # in bytes
    status = Column(String, default="READY") # READY, INVALID
    created_at = Column(DateTime, default=datetime.utcnow)

    persona = relationship("Persona", back_populates="voice_samples")

