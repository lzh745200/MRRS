"""SupportedVillage and related model factories."""

from datetime import datetime, timezone

from app.models.supported_village import (
    SupportedVillage, VillagePopulation, VillageIncome,
    ForceInvestment, IndustrySupport, InfrastructureImprovement,
    PartyBuildingSupport, MedicalSupport, ConsumptionSupport,
    EmploymentSupport, EducationSupport, SupportFunding,
)


class SupportedVillageFactory:
    @staticmethod
    def build(**kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            village_name="测试村",
            province="贵州省",
            city="贵阳市",
            county="测试县",
            township="测试镇",
            latitude=26.65,
            longitude=106.63,
            is_three_regions=False,
            is_border_area=False,
            is_ethnic_area=True,
            is_revolutionary_area=False,
            is_key_county=False,
            transition_status="none",
            created_at=now,
            updated_at=now,
        )
        data.update(kwargs)
        return SupportedVillage(**data)

    @staticmethod
    def create(db, **kwargs):
        obj = SupportedVillageFactory.build(**kwargs)
        db.add(obj)
        db.flush()
        return obj

    @staticmethod
    def build_with_full_info(**kwargs):
        kwargs.setdefault("is_three_regions", True)
        kwargs.setdefault("is_border_area", True)
        kwargs.setdefault("is_ethnic_area", True)
        kwargs.setdefault("is_revolutionary_area", True)
        kwargs.setdefault("is_key_county", True)
        kwargs.setdefault("is_provincial_demo", True)
        kwargs.setdefault("is_hundred_village_demo", True)
        kwargs.setdefault("is_tiered_development", True)
        kwargs.setdefault("is_cross_province", True)
        kwargs.setdefault("is_cross_city", True)
        kwargs.setdefault("is_cross_unit_cooperation", True)
        kwargs.setdefault("is_in_overall_plan", True)
        return SupportedVillageFactory.build(**kwargs)


class VillagePopulationFactory:
    @staticmethod
    def build(supported_village_id=1, **kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            supported_village_id=supported_village_id,
            year=2024,
            total_households=500,
            total_population=2000,
            resident_population=1800,
            labor_force=1200,
            migrant_workers=300,
            poverty_population=180,
            poverty_households=50,
            unstable_poverty_households=10,
            unstable_poverty_population=30,
            marginal_poverty_households=5,
            marginal_poverty_population=15,
            sudden_difficulty_households=3,
            sudden_difficulty_population=8,
            created_at=now,
            updated_at=now,
        )
        data.update(kwargs)
        return VillagePopulation(**data)

    @staticmethod
    def create(db, supported_village_id=1, **kwargs):
        obj = VillagePopulationFactory.build(supported_village_id=supported_village_id, **kwargs)
        db.add(obj)
        db.flush()
        return obj


class VillageIncomeFactory:
    @staticmethod
    def build(supported_village_id=1, **kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            supported_village_id=supported_village_id,
            year=2024,
            per_capita_income=12500.00,
            county_per_capita_income=12000.00,
            collective_income=200000.00,
            created_at=now,
            updated_at=now,
        )
        data.update(kwargs)
        return VillageIncome(**data)

    @staticmethod
    def create(db, supported_village_id=1, **kwargs):
        obj = VillageIncomeFactory.build(supported_village_id=supported_village_id, **kwargs)
        db.add(obj)
        db.flush()
        return obj


class SupportFundingFactory:
    @staticmethod
    def build(supported_village_id=1, **kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            supported_village_id=supported_village_id,
            year=2024,
            funding_type="total",
            military_investment=1000000.00,
            local_investment=500000.00,
            planned_investment=1500000.00,
            created_at=now,
            updated_at=now,
        )
        data.update(kwargs)
        return SupportFunding(**data)

    @staticmethod
    def create(db, supported_village_id=1, **kwargs):
        obj = SupportFundingFactory.build(supported_village_id=supported_village_id, **kwargs)
        db.add(obj)
        db.flush()
        return obj


class ForceInvestmentFactory:
    @staticmethod
    def build(supported_village_id=1, **kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            supported_village_id=supported_village_id, year=2024,
            senior_leader_visits=10, unit_soldier_visits=200,
            created_at=now, updated_at=now,
        )
        data.update(kwargs)
        return ForceInvestment(**data)

    @staticmethod
    def create(db, supported_village_id=1, **kwargs):
        obj = ForceInvestmentFactory.build(supported_village_id=supported_village_id, **kwargs)
        db.add(obj)
        db.flush()
        return obj


class IndustrySupportFactory:
    @staticmethod
    def build(supported_village_id=1, **kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            supported_village_id=supported_village_id, year=2024,
            investment=800000.00, planned_investment=1000000.00,
            planting_breeding=3, workshop=1, rural_tourism=1, other_industry=1,
            created_at=now, updated_at=now,
        )
        data.update(kwargs)
        return IndustrySupport(**data)

    @staticmethod
    def create(db, supported_village_id=1, **kwargs):
        obj = IndustrySupportFactory.build(supported_village_id=supported_village_id, **kwargs)
        db.add(obj)
        db.flush()
        return obj


class InfrastructureImprovementFactory:
    @staticmethod
    def build(supported_village_id=1, **kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            supported_village_id=supported_village_id, year=2024,
            investment=2000000.00, planned_investment=2500000.00,
            road_km=5.5, housing_renovation=50, water_facilities=3,
            cultural_plaza=1, library_cafe=1,
            created_at=now, updated_at=now,
        )
        data.update(kwargs)
        return InfrastructureImprovement(**data)

    @staticmethod
    def create(db, supported_village_id=1, **kwargs):
        obj = InfrastructureImprovementFactory.build(supported_village_id=supported_village_id, **kwargs)
        db.add(obj)
        db.flush()
        return obj


class PartyBuildingSupportFactory:
    @staticmethod
    def build(supported_village_id=1, **kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            supported_village_id=supported_village_id, year=2024,
            investment=50000.00, planned_investment=80000.00,
            paired_branches=3, party_instructors=2,
            joint_activities=12, civilization_activities=6,
            created_at=now, updated_at=now,
        )
        data.update(kwargs)
        return PartyBuildingSupport(**data)

    @staticmethod
    def create(db, supported_village_id=1, **kwargs):
        obj = PartyBuildingSupportFactory.build(supported_village_id=supported_village_id, **kwargs)
        db.add(obj)
        db.flush()
        return obj


class MedicalSupportFactory:
    @staticmethod
    def build(supported_village_id=1, **kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            supported_village_id=supported_village_id, year=2024,
            investment=300000.00, planned_investment=400000.00,
            clinics_built=1, patients_served=500,
            created_at=now, updated_at=now,
        )
        data.update(kwargs)
        return MedicalSupport(**data)

    @staticmethod
    def create(db, supported_village_id=1, **kwargs):
        obj = MedicalSupportFactory.build(supported_village_id=supported_village_id, **kwargs)
        db.add(obj)
        db.flush()
        return obj


class ConsumptionSupportFactory:
    @staticmethod
    def build(supported_village_id=1, **kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            supported_village_id=supported_village_id, year=2024,
            village_products_purchase=200000.00,
            other_products_purchase=100000.00,
            sales_counters=2, benefited_population=300,
            created_at=now, updated_at=now,
        )
        data.update(kwargs)
        return ConsumptionSupport(**data)

    @staticmethod
    def create(db, supported_village_id=1, **kwargs):
        obj = ConsumptionSupportFactory.build(supported_village_id=supported_village_id, **kwargs)
        db.add(obj)
        db.flush()
        return obj


class EmploymentSupportFactory:
    @staticmethod
    def build(supported_village_id=1, **kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            supported_village_id=supported_village_id, year=2024,
            hired_population=150, trained_population=200,
            recommended_employment=80,
            created_at=now, updated_at=now,
        )
        data.update(kwargs)
        return EmploymentSupport(**data)

    @staticmethod
    def create(db, supported_village_id=1, **kwargs):
        obj = EmploymentSupportFactory.build(supported_village_id=supported_village_id, **kwargs)
        db.add(obj)
        db.flush()
        return obj


class EducationSupportFactory:
    @staticmethod
    def build(supported_village_id=1, **kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            supported_village_id=supported_village_id, year=2024,
            investment=200000.00,
            donated_schools=1, aided_external_schools=1,
            education_activities=10, aided_students=50,
            volunteer_counselors=5,
            created_at=now, updated_at=now,
        )
        data.update(kwargs)
        return EducationSupport(**data)

    @staticmethod
    def create(db, supported_village_id=1, **kwargs):
        obj = EducationSupportFactory.build(supported_village_id=supported_village_id, **kwargs)
        db.add(obj)
        db.flush()
        return obj
