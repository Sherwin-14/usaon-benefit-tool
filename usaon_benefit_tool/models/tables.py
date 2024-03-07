"""The VTA survey data model.

WARNING: The type-checker can't save you from yourself in this file; there are many
magic strings that need to match class names at runtime.

TODO: Considered documented approach at the end of this section to mitigate above
warning:
    https://docs.sqlalchemy.org/en/14/orm/basic_relationships.html#late-evaluation-of-relationship-arguments

"""
from datetime import datetime
from functools import cache
from typing import Final, NotRequired

from flask_login import UserMixin, current_user
from sqlalchemy import CheckConstraint
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column, ForeignKey, Index, UniqueConstraint
from sqlalchemy.types import Boolean, DateTime, Enum, Integer, SmallInteger, String
from typing_extensions import TypedDict

from usaon_benefit_tool import db
from usaon_benefit_tool._types import ObservingSystemType
from usaon_benefit_tool.constants.status import STATUSES

# Workaround for missing type stubs for flask-sqlalchemy:
#     https://github.com/dropbox/sqlalchemy-stubs/issues/76#issuecomment-595839159
BaseModel: DeclarativeMeta = db.Model


# TODO: This below supports linking objects to their relationships with generic names,
# but we also need to link relationships to objects with generic names (source/target).
# That's currently implemented in a WET way below.
class IORelationship(TypedDict):
    input: NotRequired[BaseModel]
    output: NotRequired[BaseModel]


class IORelationshipMixin:
    """Provide a dictionary of input and/or output models related to this entity.

    TODO: Could use a clearer name. We may want to also have a mixin for models
    representing relationships instead of entities.
    """

    @classmethod
    @cache
    def __io__(cls) -> IORelationship:
        """Return dictionary of any IO relationships this model has.

        TODO: Fix and remove type-ignore comments.
        """
        io: IORelationship = {}
        if hasattr(cls, 'input_relationships'):
            io['input'] = cls.input_relationships.mapper.class_  # type: ignore
        if hasattr(cls, 'output_relationships'):
            io['output'] = cls.output_relationships.mapper.class_  # type: ignore

        if io == {}:
            raise RuntimeError(
                'Please only use IORelationshipMixin on a model with'
                ' input_relationships or output_relationships',
            )

        return io


class SurveyObjectFieldMixin:
    """Provide shared fields between all relationship objects to reduce repetition."""

    short_name = Column(String(256), nullable=False)
    full_name = Column(String(256), nullable=True)
    organization = Column(String(256), nullable=False)
    funder = Column(String(256), nullable=False)
    funding_country = Column(String(256), nullable=False)
    website = Column(String(256), nullable=True)
    description = Column(String(512), nullable=True)
    contact_name = Column(String(256), nullable=False)
    contact_title = Column(String(256), nullable=True)
    contact_email = Column(String(256), nullable=False)
    tags = Column(String, nullable=False)
    version = Column(String(64), nullable=True)


class User(BaseModel, UserMixin):
    __tablename__ = 'user'
    id = Column(
        Integer,
        autoincrement=True,
        primary_key=True,
    )
    # TODO: Do we want to add google_id?
    email = Column(
        # This will be email from google sso
        String,
        nullable=False,
        unique=True,
        # we want to query by email
        index=True,
    )
    name = Column(
        String,
        nullable=False,
    )
    orcid = Column(
        String(64),  # how long are orcids?
        nullable=True,
    )
    role_id = Column(
        String,
        ForeignKey('role.id'),
        default="analyst",
        nullable=False,
    )
    biography = Column(
        String,
        nullable=True,
    )
    affiliation = Column(
        String,
        nullable=True,
    )

    role = relationship('Role')
    # TODO: Rename "created_surveys"? Add "filled_surveys"?
    surveys = relationship(
        'Survey',
        back_populates='created_by',
    )


class Survey(BaseModel):
    __tablename__ = 'survey'
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    title = Column(
        String(128),
        nullable=False,
    )

    status_id = Column(
        String,
        ForeignKey('status.id'),
        default=STATUSES[0],
        nullable=False,
    )

    created_by_id = Column(
        Integer,
        ForeignKey('user.id'),
        default=(lambda: current_user.id),
        nullable=False,
    )

    created_timestamp = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )
    updated_timestamp = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )

    description = Column(
        String(512),
        nullable=True,
    )

    private = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_by = relationship(
        'User',
        back_populates='surveys',
    )
    status = relationship('Status')

    observing_systems = relationship(
        'SurveyObservingSystem',
        back_populates='survey',
    )
    data_products = relationship(
        'SurveyDataProduct',
        back_populates='survey',
    )
    applications = relationship(
        'SurveyApplication',
        back_populates='survey',
    )
    societal_benefit_areas = relationship(
        'SurveySocietalBenefitArea',
        back_populates='survey',
    )


class SurveyObservingSystem(BaseModel, IORelationshipMixin, SurveyObjectFieldMixin):
    __tablename__ = 'survey_observing_system'
    __table_args__ = (UniqueConstraint('short_name', 'survey_id'),)
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    survey_id = Column(
        Integer,
        ForeignKey('survey.id'),
        nullable=False,
    )

    type = Column(
        Enum(ObservingSystemType),
        nullable=False,
    )

    __mapper_args__: Final[dict] = {
        'polymorphic_identity': ObservingSystemType.other,
        'polymorphic_on': type,
    }

    survey = relationship(
        'Survey',
        back_populates='observing_systems',
    )
    output_relationships = relationship(
        'SurveyObservingSystemDataProduct',
        back_populates='observing_system',
        cascade="all, delete",
    )


class SurveyObservingSystemObservational(BaseModel):
    __tablename__ = 'survey_observing_system_observational'
    __mapper_args__: Final[dict] = {
        'polymorphic_identity': ObservingSystemType.observational,
    }

    survey_observing_system_id = Column(
        Integer,
        ForeignKey('survey_observing_system.id'),
        primary_key=True,
    )

    platform = Column(String(256), nullable=False)
    sensor = Column(String(256), nullable=False)


class SurveyObservingSystemResearch(BaseModel):
    __tablename__ = 'survey_observing_system_research'
    __mapper_args__: Final[dict] = {
        'polymorphic_identity': ObservingSystemType.research,
    }

    survey_observing_system_id = Column(
        Integer,
        ForeignKey('survey_observing_system.id'),
        primary_key=True,
    )

    intermediate_product = Column(String(256), nullable=False)


class SurveyDataProduct(BaseModel, IORelationshipMixin, SurveyObjectFieldMixin):
    __tablename__ = 'survey_data_product'
    __table_args__ = (UniqueConstraint('short_name', 'survey_id'),)
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    survey_id = Column(
        Integer,
        ForeignKey('survey.id'),
        nullable=False,
    )

    survey = relationship(
        'Survey',
        back_populates='data_products',
    )
    input_relationships = relationship(
        'SurveyObservingSystemDataProduct',
        back_populates='data_product',
        cascade="all, delete",
    )
    output_relationships = relationship(
        'SurveyDataProductApplication',
        back_populates='data_product',
        cascade="all, delete",
    )


class SurveyApplication(BaseModel, IORelationshipMixin, SurveyObjectFieldMixin):
    __tablename__ = 'survey_application'
    __table_args__ = (UniqueConstraint('short_name', 'survey_id'),)
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    survey_id = Column(
        Integer,
        ForeignKey('survey.id'),
        nullable=False,
    )

    # Non-application objects are colored in the diagram based on the weighted average
    # of their output links. Application objects aren't colored by that criteria because
    # it wouldn't be fair to judge poor performance in the disaster preparedness SBA for
    # an app that's not designed for that purpose. Instead, the color of the application
    # is based on the below performance rating field, and that rating is based on the
    # stated mission in the performance criteria field.
    performance_criteria = Column(String(256))
    performance_rating = Column(
        Integer,
        CheckConstraint(
            'performance_rating>0 and performance_rating<101',
            name='0-100',
        ),
        nullable=False,
    )

    survey = relationship(
        'Survey',
        back_populates='applications',
    )
    input_relationships = relationship(
        'SurveyDataProductApplication',
        back_populates='application',
        cascade="all, delete",
    )
    output_relationships = relationship(
        'SurveyApplicationSocietalBenefitArea',
        back_populates='application',
        cascade="all, delete",
    )


class SurveySocietalBenefitArea(BaseModel, IORelationshipMixin):
    __tablename__ = 'survey_societal_benefit_area'
    __table_args__ = (UniqueConstraint('societal_benefit_area_id', 'survey_id'),)
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    survey_id = Column(
        Integer,
        ForeignKey('survey.id'),
        nullable=False,
    )

    societal_benefit_area_id = Column(
        String(256),
        ForeignKey('societal_benefit_area.id'),
        nullable=False,
    )

    survey = relationship(
        'Survey',
        back_populates='societal_benefit_areas',
    )
    societal_benefit_area = relationship('SocietalBenefitArea')
    input_relationships = relationship(
        'SurveyApplicationSocietalBenefitArea',
        back_populates='societal_benefit_area',
        cascade="all, delete",
    )


# Association tables
class Status(BaseModel):
    __tablename__ = 'status'
    id = Column(
        String,
        primary_key=True,
        nullable=False,
    )


class Role(BaseModel):
    __tablename__ = 'role'
    id = Column(
        String,
        primary_key=True,
        nullable=False,
    )


class SurveyObservingSystemDataProduct(BaseModel):
    __tablename__ = 'survey_observing_system_data_product'
    __table_args__ = (
        UniqueConstraint('survey_observing_system_id', 'survey_data_product_id'),
        Index(
            f'idx_{__tablename__}',
            'survey_observing_system_id',
            'survey_data_product_id',
            unique=True,
        ),
    )
    id = Column(
        Integer,
        autoincrement=True,
        primary_key=True,
    )
    survey_observing_system_id = Column(
        Integer,
        ForeignKey('survey_observing_system.id'),
        index=True,
    )
    survey_data_product_id = Column(
        Integer,
        ForeignKey('survey_data_product.id'),
        index=True,
    )

    criticality_rating = Column(
        SmallInteger,
        CheckConstraint(
            'criticality_rating>=0 and criticality_rating<=100',
            name='c0-100',
        ),
        nullable=False,
    )
    performance_rating = Column(
        SmallInteger,
        CheckConstraint(
            'performance_rating>=0 and performance_rating<=100',
            name='0-100',
        ),
        nullable=False,
    )
    rationale = Column(String(512), nullable=True)
    needed_improvements = Column(String(512), nullable=True)

    observing_system = relationship(
        'SurveyObservingSystem',
        back_populates='output_relationships',
    )
    data_product = relationship(
        'SurveyDataProduct',
        back_populates='input_relationships',
    )

    @property
    def source(self):
        return self.observing_system

    @property
    def target(self):
        return self.data_product


class SurveyDataProductApplication(BaseModel):
    __tablename__ = 'survey_data_product_application'
    __table_args__ = (
        UniqueConstraint('survey_data_product_id', 'survey_application_id'),
        Index(
            f'idx_{__tablename__}',
            'survey_data_product_id',
            'survey_application_id',
            unique=True,
        ),
    )
    id = Column(
        Integer,
        autoincrement=True,
        primary_key=True,
    )

    survey_data_product_id = Column(
        Integer,
        ForeignKey('survey_data_product.id'),
        index=True,
    )
    survey_application_id = Column(
        Integer,
        ForeignKey('survey_application.id'),
        index=True,
    )

    criticality_rating = Column(
        SmallInteger,
        CheckConstraint(
            'criticality_rating>=0 and criticality_rating<=100',
            name='c0-100',
        ),
        nullable=False,
    )
    performance_rating = Column(
        SmallInteger,
        CheckConstraint(
            'performance_rating>=0 and performance_rating<=100',
            name='0-100',
        ),
        nullable=False,
    )
    rationale = Column(String(512), nullable=True)
    needed_improvements = Column(String(512), nullable=True)

    data_product = relationship(
        'SurveyDataProduct',
        back_populates='output_relationships',
    )
    application = relationship(
        'SurveyApplication',
        back_populates='input_relationships',
    )

    @property
    def source(self):
        return self.data_product

    @property
    def target(self):
        return self.application


class SurveyApplicationSocietalBenefitArea(BaseModel):
    __tablename__ = 'survey_application_societal_benefit_area'
    __table_args__ = (
        UniqueConstraint(
            'survey_application_id',
            'survey_societal_benefit_area_id',
        ),
        Index(
            'idx_{__tablename__}',
            'survey_application_id',
            'survey_societal_benefit_area_id',
            unique=True,
        ),
    )
    id = Column(
        Integer,
        autoincrement=True,
        primary_key=True,
    )
    survey_application_id = Column(
        Integer,
        ForeignKey('survey_application.id'),
        index=True,
    )
    survey_societal_benefit_area_id = Column(
        Integer,
        ForeignKey('survey_societal_benefit_area.id'),
        index=True,
    )

    performance_rating = Column(
        SmallInteger,
        CheckConstraint(
            'performance_rating>=0 and performance_rating<=100',
            name='0-100',
        ),
        nullable=False,
    )

    application = relationship(
        'SurveyApplication',
        back_populates='output_relationships',
    )
    societal_benefit_area = relationship(
        'SurveySocietalBenefitArea',
        back_populates='input_relationships',
    )

    @property
    def source(self):
        return self.application

    @property
    def target(self):
        return self.societal_benefit_area


# Reference tables
class SocietalBenefitArea(BaseModel):
    __tablename__ = 'societal_benefit_area'
    id = Column(
        String(256),
        primary_key=True,
    )

    societal_benefit_sub_areas = relationship(
        'SocietalBenefitSubArea',
        back_populates='societal_benefit_area',
    )


class SocietalBenefitSubArea(BaseModel):
    __tablename__ = 'societal_benefit_subarea'
    id = Column(
        String(256),
        primary_key=True,
    )
    societal_benefit_area_id = Column(
        String(256),
        ForeignKey('societal_benefit_area.id'),
        nullable=False,
    )

    societal_benefit_area = relationship(
        'SocietalBenefitArea',
        back_populates='societal_benefit_sub_areas',
    )
    societal_benefit_key_objectives = relationship(
        'SocietalBenefitKeyObjective',
        back_populates='societal_benefit_sub_area',
    )


class SocietalBenefitKeyObjective(BaseModel):
    __tablename__ = 'societal_benefit_key_objective'
    id = Column(
        String(256),
        primary_key=True,
    )
    societal_benefit_subarea_id = Column(
        String(256),
        ForeignKey('societal_benefit_subarea.id'),
        primary_key=True,
    )

    societal_benefit_sub_area = relationship(
        'SocietalBenefitSubArea',
        back_populates='societal_benefit_key_objectives',
    )


SurveyNode = (
    SurveyObservingSystem
    | SurveyDataProduct
    | SurveyApplication
    | SurveySocietalBenefitArea
)
