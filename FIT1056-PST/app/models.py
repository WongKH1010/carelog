from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Date, Text, Time
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import date, time
from enum import IntEnum

db = SQLAlchemy()

class Base(DeclarativeBase):
    pass

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String, nullable=False)
    gender: Mapped[str] = mapped_column(String)
    dob: Mapped[date] = mapped_column(Date)
    contact: Mapped[str] = mapped_column(String)
    role_level: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_profile = relationship("PatientProfile", back_populates="patient", uselist=False)
    appointments = relationship("Appointment", primaryjoin="or_(User.id==Appointment.doctor_id,"
                                                           "User.id==Appointment.patient_id)", viewonly=True)

class PatientProfile(db.Model):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cultural: Mapped[str] = mapped_column(Text, nullable=True)
    dietary: Mapped[str] = mapped_column(Text, nullable=True)
    allergens: Mapped[str] = mapped_column(Text, nullable=True)
    medical_history: Mapped[str] = mapped_column(Text, nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    risk_level: Mapped[str] = mapped_column(String, nullable=True)
    patient = relationship("User", back_populates="patient_profile")
    patient_logs = relationship("PatientLog", back_populates="patient")

class Appointment(db.Model):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    time: Mapped[time] = mapped_column(Time, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)
    doctor_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=True)
    patient_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=True)
    doctor = relationship("User", foreign_keys=doctor_id)
    patient = relationship("User", foreign_keys=patient_id)

class PatientLog(db.Model):
    __tablename__ = "patient_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    time: Mapped[time] = mapped_column(Time, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer)
    medical: Mapped[str] = mapped_column(Text, nullable=True)
    emotional: Mapped[str] = mapped_column(Text, nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=True)
    patient_note: Mapped[str] = mapped_column(Text, nullable=True)
    profile_id: Mapped[int] = mapped_column(db.ForeignKey("patients.id"))
    patient = relationship("PatientProfile", back_populates="patient_logs")

class Role(IntEnum):
    PATIENT = 0
    RECEPTIONIST = 1
    NURSE = 2
    DOCTOR = 3
    ADMIN = 4