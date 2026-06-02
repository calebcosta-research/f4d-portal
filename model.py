import datetime
from sqlalchemy import Column, Enum, Float, Integer, String, Table, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Session
from enum import Enum as PyEnum

Base = declarative_base()


class Indicator(Base):
    __tablename__ = 'indicators'
    __table_args__ = {'schema': 'TF_RESULTS_REPORTING'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    indicator_id = Column(String, nullable=False)
    parent_id = Column(String, nullable=True)
    indicator_name = Column(Text, nullable=False)
    standard_indicator_name = Column(Text, nullable=True)
    indicator_prompt = Column(Text, nullable=True)
    pillar_info = Column(String, nullable=True)
    tier_info = Column(String, nullable=True)
    indicator_definition = Column(Text, nullable=True)
    unit_of_measurement = Column(
        Enum('', 'Date', 'Number', 'Short Text', 'Long Text', 'Percentage', 'Categorical', name='unit_enum'), nullable=True)
    categorical_unit = Column(Text, nullable=True)
    indicator_conversion = Column(String, nullable=True)
    custom_indicator = Column(Boolean, default=True)
    team_id = Column(Integer, ForeignKey('TF_RESULTS_REPORTING.teams.id'), nullable=True)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    team = relationship("Team", backref="indicators")

    def __repr__(self):
        return f"<Indicator(id={self.id}, name={self.indicator_name})>"


class Team(Base):
    __tablename__ = 'teams'
    __table_args__ = {'schema': 'TF_RESULTS_REPORTING'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    team = Column(String, nullable=False)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    # Define the relationship here using a string
    users = relationship("User", order_by="User.id", back_populates="team")

    def __repr__(self):
        return f"<Team(id={self.id}, name={self.team})>"

    @classmethod
    def can_delete(cls, session: Session, team_id: int) -> bool:
        """Check if the Team can be deleted."""
        return not session.query(User).filter_by(team_id=team_id).first()


# Function to delete a team
def delete_team(session: Session, team_id: int) -> bool:
    """Delete a team if it has no associated users."""
    if Team.can_delete(session, team_id):
        team_to_delete = session.query(Team).filter_by(id=team_id).first()
        if team_to_delete:
            # Mark the team as deleted (soft delete)
            team_to_delete.deleted = True
            team_to_delete.updated_at = datetime.datetime.now()
            session.commit()
            return True
    return False


class FiscalYear(Base):
    __tablename__ = 'fys'
    __table_args__ = {'schema': 'TF_RESULTS_REPORTING'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    fy = Column(String, nullable=False)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"{self.fy}"


class User(Base):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'TF_RESULTS_REPORTING'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    team_id = Column(Integer, ForeignKey('TF_RESULTS_REPORTING.teams.id'),
                     nullable=True)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    team = relationship("Team", back_populates="users")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, team_id={self.team_id})>"


class Country(Base):
    __tablename__ = 'countries'
    __table_args__ = {'schema': 'TF_RESULTS_REPORTING'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    country = Column(String, nullable=False)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<Country(id={self.id}, name={self.country})>"


class Region(Base):
    __tablename__ = 'regions'
    __table_args__ = {'schema': 'TF_RESULTS_REPORTING'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    region = Column(String, nullable=False)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<Region(id={self.id}, name={self.region})>"


class TrustFund(Base):
    __tablename__ = 'trustfunds'
    __table_args__ = {'schema': 'TF_RESULTS_REPORTING'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_type = Column(Enum('Trust Fund', 'Pillar', 'Tier',
                               name='type_enum'), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    pcode = Column(String, nullable=True)
    grant = Column(String, nullable=True)
    ttl = Column(String, nullable=True)
    team_id = Column(Integer, ForeignKey('TF_RESULTS_REPORTING.teams.id'), nullable=True)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    team = relationship("Team", backref="projects")

    def __repr__(self):
        return f"<TrustFunds(id={self.id}, type={self.type}, name={self.name}, description={self.description})>"


class TrustFundIndicatorMapping(Base):
    __tablename__ = 'trustfund_indicator_mapping'
    __table_args__ = {'schema': 'TF_RESULTS_REPORTING'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    trustfund_id = Column(Integer, ForeignKey('TF_RESULTS_REPORTING.trustfunds.id'), nullable=False)
    indicator_id = Column(Integer, ForeignKey('TF_RESULTS_REPORTING.indicators.id'), nullable=False)
    relation_ship = Column(Enum('Mandatory', 'Optional',
                                name='relationship_enum'), nullable=False)
    team_id = Column(Integer, ForeignKey('TF_RESULTS_REPORTING.teams.id'), nullable=True)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    team = relationship("Team", backref="trustfund_indicators")
    trustfund = relationship("TrustFund", backref="trustfund_indicators")
    indicator = relationship("Indicator", backref="trustfund_indicators")

    def __repr__(self):
        return f"<TrustFundIndicatorMapping(id={self.id}, trustfund_id={self.trustfund_id}, indicator_id={self.indicator_id})>"


class F4DAssociationEnum(PyEnum):
    SOLELY_F4D = "Yes, this P code is used solely for F4D funded activities"
    OTHER_FUNDING = "No, this P code is used for activities supported by other funding sources (e.g., other Trust Funds) as well."



# class GrantInfo(Base):
#     __tablename__ = 'grant_info'
#     __table_args__ = {'schema': 'TF_RESULTS_REPORTING'}

#     id = Column(Integer, primary_key=True)
#     # 1.	Basic Grant Information
#     trustfund_id = Column(Integer, ForeignKey('TF_RESULTS_REPORTING.trustfunds.id'), nullable=False)
#     fiscal_year_id = Column(Integer, ForeignKey('TF_RESULTS_REPORTING.fys.id'), nullable=True)
#     country = Column(Text)
#     p_code_instrument = Column(Text)
#     p_code_description = Column(String)
#     f4d_association = Column(Enum(F4DAssociationEnum), nullable=True)
#     region_id = Column(Integer, ForeignKey('TF_RESULTS_REPORTING.regions.id'), nullable=True)
#     pillars = Column(Text)
#     ccts = Column(Text)
#     pillar_explanations = Column(Text)
#     cct_explanations = Column(Text)

#     trustfund = relationship("TrustFund", backref="grant_infos")
#     fiscal_year = relationship("FiscalYear", backref="grant_infos")
#     region = relationship("Region", backref="grant_infos")
#     team = relationship("Team", backref="grant_infos")

#     # 2. Strategic Objective & Progress
#     challenges = Column(Text)
#     strategic_objective = Column(Text)
#     overall_progress = Column(Text)
#     implementation_challenges = Column(Text)
#     public_communication_external = Column(Text)
#     public_communication_internal = Column(Text)

#     # 3. Lending operations
#     operations = Column(Text)
#     cpfs = Column(Text)

#     # 4.	Collaboration/Partnership
#     collaborations = Column(Text)
#     other_teams = Column(String)
#     other_ifis = Column(String)
#     other_orgs = Column(String)
#     describe_collaboration = Column(Text)
#     lessons_learned = Column(Text)

#     # 5. Deliverables
#     deliverables = Column(Text)

#     # 6. Indicators
#     indicators = Column(Text)

#     # 6. Custom Indicators
#     custom_indicators = Column(Text)

#     team_id = Column(Integer, ForeignKey('TF_RESULTS_REPORTING.teams.id'), nullable=True)
#     deleted = Column(Boolean, default=False)
#     created_at = Column(DateTime, nullable=False)
#     updated_at = Column(DateTime, nullable=False)


class GrantInfo(Base):
    __tablename__ = 'grant_info_long'
    __table_args__ = {'schema': 'TF_RESULTS_REPORTING'}

    id = Column(Integer, primary_key=True)
    trustfund_id = Column(Integer, ForeignKey('TF_RESULTS_REPORTING.trustfunds.id'), nullable=False)
    fiscal_year_id = Column(Integer, ForeignKey('TF_RESULTS_REPORTING.fys.id'), nullable=True)
    field = Column(String, nullable=False)
    value = Column(Text, nullable=True)

    trustfund = relationship("TrustFund", backref="grant_info_long")
    fiscal_year = relationship("FiscalYear", backref="grant_info_long")
    team = relationship("Team", backref="grant_info_long")

    team_id = Column(Integer, ForeignKey('TF_RESULTS_REPORTING.teams.id'), nullable=True)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)