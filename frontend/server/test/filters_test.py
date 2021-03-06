"""Tests for filters in the bob_emploi.frontend.scoring module."""

import datetime
import unittest

import mock

from bob_emploi.frontend.api import job_pb2
from bob_emploi.frontend.api import project_pb2
from bob_emploi.frontend.api import user_pb2
from bob_emploi.frontend.server import companies
from bob_emploi.frontend.server import scoring
from bob_emploi.frontend.server.test import scoring_test


# TODO(pasca): Split in several test modules and remove following comment.
# pylint: disable=too-many-lines


def FilterTestBase(model_id):  # pylint: disable=invalid-name
    """A base class for tests for filters."""

    class _TestCase(scoring_test.ScoringModelTestBase(model_id)):

        def setUp(self):
            super(_TestCase, self).setUp()
            self.persona = self._random_persona().clone()

        def _assert_pass_filter(self):
            score = self._score_persona(self.persona)
            self.assertGreater(score, 0, msg='Failed for "{}"'.format(self.persona.name))

        def _assert_fail_filter(self):
            score = self._score_persona(self.persona)
            self.assertLessEqual(score, 0, msg='Failed for "{}"'.format(self.persona.name))

    return _TestCase


class ActiveSearcherFilterTestCase(FilterTestBase('for-active-search')):
    """Unit tests for the _ProjectFilter class for users that have started their search."""

    def test_active_searcher(self):
        """Users that have already started their search."""

        self.persona.project.job_search_has_not_started = False
        self._assert_pass_filter()

    def test_inactive_searcher(self):
        """Users that have not yet started their search."""

        self.persona.project.job_search_has_not_started = True
        self._assert_fail_filter()


class EnoughTrainingFilterTestCase(FilterTestBase('for-training-fulfilled')):
    """Unit tests for the _ProjectFilter class for users with sufficient training."""

    def test_enough_training(self):
        """Users that have sufficient training."""

        self.persona.project.training_fulfillment_estimate = project_pb2.ENOUGH_DIPLOMAS
        self._assert_pass_filter()

    def test_not_enough_training(self):
        """Users that have not sufficient training."""

        self.persona.project.training_fulfillment_estimate = project_pb2.CURRENTLY_IN_TRAINING
        self._assert_fail_filter()


class SingleParentFilterTestCase(FilterTestBase('for-single-parent')):
    """Unit tests for the _UserProfileFilter class for single parents."""

    def test_single_parent(self):
        """Single parent."""

        self.persona.user_profile.family_situation = user_pb2.SINGLE_PARENT_SITUATION
        self._assert_pass_filter()

    def test_single_parent_old_field(self):
        """Single parent using the old field."""

        self.persona.user_profile.frustrations.append(user_pb2.SINGLE_PARENT)
        self._assert_pass_filter()

    def test_non_single_parent(self):
        """Non single parent."""

        del self.persona.user_profile.frustrations[:]
        self.persona.user_profile.family_situation = user_pb2.IN_A_RELATIONSHIP
        self._assert_fail_filter()


class YoungFilterTestCase(FilterTestBase('for-young(25)')):
    """Unit tests for the _UserProfileFilter class for young people."""

    year = datetime.date.today().year

    def test_young_person(self):
        """Young person."""

        self.persona.user_profile.year_of_birth = self.year - 21
        self._assert_pass_filter()

    def test_old_person(self):
        """Old person."""

        self.persona.user_profile.year_of_birth = self.year - 28
        self._assert_fail_filter()


class ApplicantFilterTestCase(FilterTestBase('for-application(2)')):
    """Unit tests for the _ProjectFilter class for users that have applied for some jobs."""

    def test_had_applied(self):
        """User have applied three times per week."""

        self.persona.project.weekly_applications_estimate = project_pb2.DECENT_AMOUNT
        self._assert_pass_filter()

    def test_had_not_applied(self):
        """User have never applied."""

        self.persona.project.weekly_applications_estimate = -1
        self._assert_fail_filter()

    def test_had_unknown_application(self):
        """User have never applied."""

        self.persona.project.weekly_applications_estimate = 0
        self._assert_fail_filter()


class InterviewFilterTestCase(FilterTestBase('for-many-interviews(2)')):
    """Unit tests for the _ProjectFilter class for users that have had some interviews."""

    def test_had_interviews(self):
        """User have had three interviews."""

        self.persona.project.total_interview_count = 3
        self._assert_pass_filter()

    def test_had_no_interview(self):
        """User have had no interviews."""

        self.persona.project.total_interview_count = -1
        self._assert_fail_filter()


class ExactInterviewFilterTestCase(FilterTestBase('for-exact-interview(1)')):
    """Unit tests for the _ProjectFilter class for users that have had exactly one interview."""

    def test_had_interviews(self):
        """User have had three interviews."""

        self.persona.project.total_interview_count = 3
        self._assert_fail_filter()

    def test_had_one_interview(self):
        """User have had one interview."""

        self.persona.project.total_interview_count = 1
        self._assert_pass_filter()

    def test_had_no_interview(self):
        """User have had no interviews."""

        self.persona.project.total_interview_count = -1
        self._assert_fail_filter()


class InterviewSmallRateFilterTestCase(FilterTestBase('for-many-interviews-per-month(0.5)')):
    """Unit tests for the _ProjectFilter class for users that have had exactly one interview."""

    def test_had_interviews(self):
        """User have had three interviews in two months."""

        self.persona.project.job_search_length_months = 2
        self.persona.project.job_search_started_at.FromDatetime(
            self.persona.project.created_at.ToDatetime() - datetime.timedelta(days=61))
        self.persona.project.total_interview_count = 3
        self._assert_pass_filter()

    def test_had_few_interviews(self):
        """User have had few interviews."""

        self.persona.project.job_search_length_months = 5
        self.persona.project.job_search_started_at.FromDatetime(
            self.persona.project.created_at.ToDatetime() - datetime.timedelta(days=152.5))
        self.persona.project.total_interview_count = 2
        self._assert_fail_filter()


class InterviewRateFilterTestCase(FilterTestBase('for-many-interviews-per-month(1)')):
    """Unit tests for the _ProjectFilter class for users that have had exactly one interview."""

    def test_had_interviews(self):
        """User have had three interviews in two months."""

        self.persona.project.job_search_length_months = 2
        self.persona.project.job_search_started_at.FromDatetime(
            self.persona.project.created_at.ToDatetime() - datetime.timedelta(days=61))
        self.persona.project.total_interview_count = 3
        self._assert_pass_filter()

    def test_had_few_interviews(self):
        """User have had few interviews."""

        self.persona.project.job_search_length_months = 2
        self.persona.project.job_search_started_at.FromDatetime(
            self.persona.project.created_at.ToDatetime() - datetime.timedelta(days=61))
        self.persona.project.total_interview_count = 1
        self._assert_fail_filter()


class NoInterviewFilterTestCase(FilterTestBase('for-no-interview')):
    """Unit tests for the _ProjectFilter class for users that have had some interviews."""

    def test_had_interviews(self):
        """User have had three interviews."""

        self.persona.project.total_interview_count = 3
        self._assert_fail_filter()

    def test_had_unknown_interviews(self):
        """User have had three interviews."""

        self.persona.project.total_interview_count = 0
        self._assert_fail_filter()

    def test_had_no_interview(self):
        """User have had no interviews."""

        self.persona.project.total_interview_count = -1
        self._assert_pass_filter()


class OldFilterTestCase(FilterTestBase('for-old(50)')):
    """Unit tests for the _UserProfileFilter class for old people."""

    year = datetime.date.today().year

    def test_young_person(self):
        """Young person."""

        self.persona.user_profile.year_of_birth = self.year - 21
        self._assert_fail_filter()

    def test_mature_person(self):
        """Mature person."""

        self.persona.user_profile.year_of_birth = self.year - 45
        self._assert_fail_filter()

    def test_very_old_person(self):
        """Old person."""

        self.persona.user_profile.year_of_birth = self.year - 60
        self._assert_pass_filter()


class FrustratedOldFilterTestCase(FilterTestBase('for-frustrated-old(50)')):
    """Unit tests for the _UserProfileFilter class for 50 yo frustrated old people."""

    year = datetime.date.today().year

    def test_young_person(self):
        """Young person."""

        self.persona.user_profile.year_of_birth = self.year - 21
        self._assert_fail_filter()

    def test_old_person(self):
        """Old person."""

        self.persona.user_profile.year_of_birth = self.year - 60
        del self.persona.user_profile.frustrations[:]
        self._assert_fail_filter()

    def test_not_so_old_frustrated_person(self):
        """Old and frustrated person."""

        self.persona.user_profile.year_of_birth = self.year - 47
        self.persona.user_profile.frustrations.append(user_pb2.AGE_DISCRIMINATION)
        self._assert_fail_filter()

    def test_old_frustrated_person(self):
        """Old and frustrated person."""

        self.persona.user_profile.year_of_birth = self.year - 60
        self.persona.user_profile.frustrations.append(user_pb2.AGE_DISCRIMINATION)
        self._assert_pass_filter()


class OtherFrustratedOldFilterTestCase(FilterTestBase('for-frustrated-old(45)')):
    """Unit tests for the _UserProfileFilter class for 45 yo frustrated old people."""

    year = datetime.date.today().year

    def test_young_person(self):
        """Young person."""

        self.persona.user_profile.year_of_birth = self.year - 21
        self._assert_fail_filter()

    def test_old_person(self):
        """Old person."""

        self.persona.user_profile.year_of_birth = self.year - 60
        del self.persona.user_profile.frustrations[:]
        self._assert_fail_filter()

    def test_old_frustrated_person(self):
        """Old and frustrated person."""

        self.persona.user_profile.year_of_birth = self.year - 47
        self.persona.user_profile.frustrations.append(user_pb2.AGE_DISCRIMINATION)
        self._assert_pass_filter()


class FrustratedYoungFilterTestCase(FilterTestBase('for-frustrated-young(25)')):
    """Unit tests for the _UserProfileFilter class for frustrated young people."""

    year = datetime.date.today().year

    def test_young_person(self):
        """Young person."""

        self.persona.user_profile.year_of_birth = self.year - 21
        del self.persona.user_profile.frustrations[:]
        self._assert_fail_filter()

    def test_old_frustrated_person(self):
        """Old and frustrated person."""

        self.persona.user_profile.year_of_birth = self.year - 60
        self.persona.user_profile.frustrations.append(user_pb2.AGE_DISCRIMINATION)
        self._assert_fail_filter()

    def test_young_frustrated_person(self):
        """Young and frustrated person."""

        self.persona.user_profile.year_of_birth = self.year - 21
        self.persona.user_profile.frustrations.append(user_pb2.AGE_DISCRIMINATION)
        self._assert_pass_filter()


class UnemployedFilterTestCase(FilterTestBase('for-unemployed')):
    """Unit tests for the _UserProfileFilter class for unemployed."""

    def test_lost_quit(self):
        """User lost or quit their last job."""

        self.persona.user_profile.situation = user_pb2.LOST_QUIT
        self._assert_pass_filter()

    def test_student(self):
        """Student."""

        self.persona.user_profile.situation = user_pb2.FIRST_TIME
        self._assert_pass_filter()

    def test_employed(self):
        """User has a job."""

        self.persona.user_profile.situation = user_pb2.EMPLOYED
        self._assert_fail_filter()


class EmployedFilterTestCase(FilterTestBase('for-employed')):
    """Unit tests for the BaseFilter class for employed."""

    def test_first_job(self):
        """This is the first job for the user."""

        self.persona.user_profile.situation = user_pb2.FIRST_TIME
        self.persona.project.kind = project_pb2.FIND_A_FIRST_JOB
        self._assert_fail_filter()

    def test_looking_for_another_job(self):
        """User is looking for another job (so they already have one)."""

        self.persona.project.kind = project_pb2.FIND_ANOTHER_JOB
        self._assert_pass_filter()

    def test_employed(self):
        """User has a job."""

        self.persona.user_profile.situation = user_pb2.EMPLOYED
        self._assert_pass_filter()


class NotEmployedAnymoreFilterTestCase(FilterTestBase('for-not-employed-anymore')):
    """Unit tests for the _UserProfileFilter class for users that lost or quit their last job."""

    def test_lost_quit(self):
        """User lost or quit their last job."""

        self.persona.user_profile.situation = user_pb2.LOST_QUIT
        self._assert_pass_filter()

    def test_student(self):
        """Student."""

        self.persona.user_profile.situation = user_pb2.FIRST_TIME
        self._assert_fail_filter()

    def test_employed(self):
        """User has a job."""

        self.persona.user_profile.situation = user_pb2.EMPLOYED
        self._assert_fail_filter()


class QualifiedFilterTestCase(FilterTestBase('for-qualified(bac+3)')):
    """Unit tests for the _UserProfileFilter class for users that are qualified."""

    def test_phd(self):
        """User has a PhD."""

        self.persona.user_profile.highest_degree = job_pb2.DEA_DESS_MASTER_PHD
        self._assert_pass_filter()

    def test_no_degree(self):
        """User has no degree."""

        self.persona.user_profile.highest_degree = job_pb2.NO_DEGREE
        self._assert_fail_filter()

    def test_dut(self):
        """User has a DUT."""

        self.persona.user_profile.highest_degree = job_pb2.BTS_DUT_DEUG
        self._assert_fail_filter()


class NegateFilterTestCase(FilterTestBase('not-for-searching-forever')):
    """Unit tests for the negate filter."""

    def test_just_started(self):
        """User has just started this project."""

        self.persona.project.job_search_length_months = 1
        self.persona.project.job_search_started_at.FromDatetime(
            self.persona.project.created_at.ToDatetime() - datetime.timedelta(days=30.5))
        self._assert_pass_filter()

    def test_started_2_years_ago(self):
        """User has been working on this project for 2 years."""

        self.persona.project.job_search_length_months = 24
        self.persona.project.job_search_started_at.FromDatetime(
            self.persona.project.created_at.ToDatetime() - datetime.timedelta(days=732))
        self._assert_fail_filter()


class SearchingForeverFilterTestCase(FilterTestBase('for-searching-forever')):
    """Unit tests for the _ProjectFilter class for projects about searching for a looong time."""

    def test_just_started(self):
        """User has just started this project."""

        self.persona.project.job_search_length_months = 1
        self.persona.project.job_search_started_at.FromDatetime(
            self.persona.project.created_at.ToDatetime() - datetime.timedelta(days=30.5))
        self._assert_fail_filter()

    def test_started_2_years_ago(self):
        """User has been working on this project for 2 years."""

        self.persona.project.job_search_length_months = 24
        self.persona.project.job_search_started_at.FromDatetime(
            self.persona.project.created_at.ToDatetime() - datetime.timedelta(days=732))
        self._assert_pass_filter()


class JobGroupFilterTestCase(FilterTestBase('for-job-group(M16)')):
    """Unit tests for the _JobGroupFilter class for projects about M16* job groups."""

    def test_secretary(self):
        """User is looking for a secretary job."""

        self.persona.project.target_job.job_group.rome_id = 'M1601'
        self._assert_pass_filter()

    def test_data_scientist(self):
        """User is looking for a data scientist job."""

        self.persona.project.target_job.job_group.rome_id = 'M1403'
        self._assert_fail_filter()


class HighSalaryFilterTestCase(FilterTestBase('for-high-salary-expectations')):
    """Unit tests for the _BaseFilter class for projects with expectations above median salary."""

    def test_high_expectations(self):
        """User is looking for a secretary job."""

        self.persona.project.target_job.job_group.rome_id = 'M1601'
        self.persona.project.mobility.city.departement_id = '19'
        self.persona.project.min_salary = 22000
        self.database.local_diagnosis.insert_one({
            '_id': '19:M1601',
            'salary': {'medianSalary': 20000},
        })
        self._assert_pass_filter()

    def test_low_expectations(self):
        """User is looking for a secretary job."""

        self.persona.project.target_job.job_group.rome_id = 'M1602'
        self.persona.project.mobility.city.departement_id = '19'
        self.persona.project.min_salary = 18000
        self.database.local_diagnosis.insert_one({
            '_id': '19:M1602',
            'salary': {'medianSalary': 20000},
        })
        self._assert_fail_filter()


class HighMarketStressFilterTestCase(FilterTestBase('for-unstressed-market(10/7)')):
    """Unit tests for the _BaseFilter class for projects with low market stress."""

    def test_low_market_stress(self):
        """User looking for a job that had 7 offers per 10 candidates."""

        self.persona.project.target_job.job_group.rome_id = 'M1601'
        self.persona.project.mobility.city.departement_id = '19'
        self.database.local_diagnosis.insert_one({
            '_id': '19:M1601',
            'imt': {
                'yearlyAvgOffersDenominator': 10,
                'yearlyAvgOffersPer10Candidates': 7,
            }
        })
        self._assert_pass_filter()

    def test_high_market_stress(self):
        """User looking for a job that had 6 offers per 10 candidates."""

        self.persona.project.target_job.job_group.rome_id = 'M1602'
        self.persona.project.mobility.city.departement_id = '19'
        self.database.local_diagnosis.insert_one({
            '_id': '19:M1602',
            'imt': {
                'yearlyAvgOffersDenominator': 10,
                'yearlyAvgOffersPer10Candidates': 5,
            }
        })
        self._assert_fail_filter()

    # This should never happen but we test it anyway to be sure it doesn't crash.
    def test_zero_market_stress(self):
        """User looking for a job that had no offers."""

        self.persona.project.target_job.job_group.rome_id = 'M1602'
        self.persona.project.mobility.city.departement_id = '19'
        self.database.local_diagnosis.insert_one({
            '_id': '19:M1602',
            'imt': {
                'yearlyAvgOffersDenominator': 10,
                'yearlyAvgOffersPer10Candidates': 0,
            }
        })
        self._assert_fail_filter()


class ExperienceInDomainTestCase(FilterTestBase('for-experience-in-domain')):
    """Unit tests for the _ProjectFilter class for users with previous experience in the domain."""

    def test_high_expectations(self):
        """User have experience in the domain in which they are searching."""

        self.persona.project.previous_job_similarity = project_pb2.DONE_THIS
        self._assert_pass_filter()

    def test_low_expectations(self):
        """User does not have experience in the domain in which they are searching."""

        self.persona.project.previous_job_similarity = project_pb2.DONE_SIMILAR
        self._assert_fail_filter()


class ExperienceInSimilarDomainTestCase(FilterTestBase('for-experience-in-similar-domain')):
    """Unit tests for the _ProjectFilter class for users with previous experience in similar domain.
    """

    def test_high_expectations(self):
        """User have experience in a similar domain to the one in which they are searching."""

        self.persona.project.previous_job_similarity = project_pb2.DONE_SIMILAR
        self._assert_pass_filter()

    def test_low_expectations(self):
        """User does not have experience in a similar domain to the one in which they are searching.
        """

        self.persona.project.previous_job_similarity = project_pb2.DONE_THIS
        self._assert_fail_filter()


class NoExperienceInDomainTestCase(FilterTestBase('for-first-time-in-job')):
    """Unit tests for the _ProjectFilter class for users with previous experience in the domain."""

    def test_high_expectations(self):
        """User have experience in the domain in which they are searching or similar."""

        self.persona.project.previous_job_similarity = project_pb2.DONE_SIMILAR
        self._assert_fail_filter()

    def test_low_expectations(self):
        """User does not have experience in the domain in which they are searching."""

        self.persona.project.previous_job_similarity = project_pb2.NEVER_DONE
        self._assert_pass_filter()


class MultiJobGroupFilterTestCase(FilterTestBase('for-job-group(L15,L13)')):
    """Unit tests for the _JobGroupFilter class for projects about L15* or L13* job groups."""

    def test_secretary(self):
        """User is looking for a secretary job."""

        self.persona.project.target_job.job_group.rome_id = 'M1601'
        self._assert_fail_filter()

    def test_first_job_group(self):
        """User is looking for a job in the first group of the list."""

        self.persona.project.target_job.job_group.rome_id = 'L1502'
        self._assert_pass_filter()

    def test_second_job_group(self):
        """User is looking for a job in the second group of the list."""

        self.persona.project.target_job.job_group.rome_id = 'L1302'
        self._assert_pass_filter()


class JobFilterTestCase(FilterTestBase('for-job(12006)')):
    """Unit tests for the _JobFilter class for projects about 12006 job."""

    def test_chief_baker(self):
        """User is looking for a chief baker job."""

        self.persona.project.target_job.code_ogr = '12006'
        self._assert_pass_filter()

    def test_prefix(self):
        """User is looking for a job that starts with the chief baker code."""

        self.persona.project.target_job.code_ogr = '120060'
        self._assert_fail_filter()


class FrustrationFilterTestCase(FilterTestBase('for-frustrated(INTERVIEW)')):
    """Unit tests for the FrustrationFilter class for projects about INTERVIEW frustration."""

    def test_frustrated_user(self):
        """User is frustrated by their interviews."""

        self.persona.user_profile.frustrations.append(user_pb2.INTERVIEW)
        self._assert_pass_filter()

    def test_not_frustrated(self):
        """User has no frustration."""

        self.persona.user_profile.ClearField('frustrations')
        self._assert_fail_filter()


class UnknownFrustrationFilterTestCase(unittest.TestCase):
    """Unit test for the FrustrationFilter class for projects about a
    frustration that does not exist."""

    def test_inexistant_frustration(self):
        """Cannot make scoring model for inexistant frustration."""

        with self.assertRaises(ValueError):
            scoring.get_scoring_model('for-frustrated(INEXISTANT)')


class DepartementFilterTestCase(FilterTestBase('for-departement(31)')):
    """Unit tests for the _DepartementFilter class for projects about département 31."""

    def test_toulouse(self):
        """User is looking for a job in Toulouse."""

        self.persona.project.mobility.city.departement_id = '31'
        self._assert_pass_filter()

    def test_lyon(self):
        """User is looking for a job in Lyon."""

        self.persona.project.mobility.city.departement_id = '69'
        self._assert_fail_filter()


class MultiDepartementFilterTestCase(FilterTestBase('for-departement(31, 69)')):
    """Unit tests for the _DepartementFilter class for projects about multiple départements."""

    def test_toulouse(self):
        """User is looking for a job in Toulouse."""

        self.persona.project.mobility.city.departement_id = '31'
        self._assert_pass_filter()

    def test_lyon(self):
        """User is looking for a job in Lyon."""

        self.persona.project.mobility.city.departement_id = '69'
        self._assert_pass_filter()

    def test_paris(self):
        """User is looking for a job in Paris."""

        self.persona.project.mobility.city.departement_id = '75'
        self._assert_fail_filter()


class FilterApplicationComplexityTestCase(FilterTestBase('for-complex-application')):
    """Unit tests for the _ApplicationComplexityFilter class."""

    def test_special_complexity(self):
        """User is in a job with a special complexity."""

        self.persona.project.target_job.job_group.rome_id = 'M1601'
        self.database.job_group_info.insert_one({
            '_id': 'M1601', 'applicationComplexity': 'SPECIAL_APPLICATION_PROCESS'})
        self._assert_fail_filter()

    def test_complex_application(self):
        """User is in a job with a complex application process."""

        self.persona.project.target_job.job_group.rome_id = 'M1601'
        self.database.job_group_info.insert_one({
            '_id': 'M1601', 'applicationComplexity': 'COMPLEX_APPLICATION_PROCESS'})
        self._assert_pass_filter()


class FilterActiveExperimentTestCase(FilterTestBase('for-active-experiment(lbb_integration)')):
    """Unit tests for the _ActiveExperimentFilter class."""

    def test_in_control(self):
        """User is in the control group."""

        self.persona.features_enabled.lbb_integration = user_pb2.CONTROL
        self._assert_fail_filter()

    def test_not_in_experiment(self):
        """User is not in the experiment at all."""

        self.persona.features_enabled.ClearField('lbb_integration')
        self._assert_fail_filter()

    def test_in_experiment(self):
        """User is in the experiment."""

        self.persona.features_enabled.lbb_integration = user_pb2.ACTIVE
        self._assert_pass_filter()


class FilterActiveUnknownExperimentTestCase(unittest.TestCase):
    """Unit tests for the _ActiveExperimentFilter class when experiment does not exist."""

    def test_unknown_field(self):
        """Tries to create a filter based on an experiment that does not exist."""

        with self.assertRaises(ValueError):
            scoring.get_scoring_model('for-active-experiment(unknown)')

    def test_wrong_type_field(self):
        """Tries to create a filter based on a field that is not a binary experiment."""

        with self.assertRaises(ValueError):
            scoring.get_scoring_model('for-active-experiment(alpha)')


class FilterGoodOverallScoreTestCase(FilterTestBase('for-good-overall-score(50)')):
    """Unit tests for the for-good-overall-score filter."""

    def test_low_score(self):
        """Low score."""

        self.persona.project.diagnostic.overall_score = 30
        self._assert_fail_filter()

    def test_high_score(self):
        """High score."""

        self.persona.project.diagnostic.overall_score = 90
        self._assert_pass_filter()


class FilterGoodNetworkScoreTestCase(FilterTestBase('for-network(3)')):
    """Unit tests for the for-network(3) filter."""

    def test_lower_network_estimation(self):
        """User only has a medium network."""

        self.persona.project.network_estimate = 2
        self._assert_fail_filter()

    def test_high_score(self):
        """User only has a good network."""

        self.persona.project.network_estimate = 3
        self._assert_pass_filter()


class FilterPassionateLevelTestCase(FilterTestBase('for-passionate(LIFE_GOAL_JOB)')):
    """Unit tests for the for-passionate-level(LIFE_GOAL_JOB) filter."""

    def test_not_really_passionate(self):
        """User only likes their job."""

        self.persona.project.passionate_level = project_pb2.LIKEABLE_JOB
        self._assert_fail_filter()

    def test_passionate(self):
        """User is really fond of their job."""

        self.persona.project.passionate_level = project_pb2.LIFE_GOAL_JOB
        self._assert_pass_filter()


class UnknownPassionateFilterTestCase(unittest.TestCase):
    """Unit test for the PassionateFilter class for projects about a
    passionate level that does not exist."""

    def test_inexistant_passionate(self):
        """Cannot make scoring model for inexistant passionate level."""

        with self.assertRaises(ValueError):
            scoring.get_scoring_model('for-passionate(INEXISTANT)')


class FilterShortSearchTestCase(FilterTestBase('for-short-search(-3)')):
    """Unit tests for the for-short-search(-3) filter."""

    def test_just_started(self):
        """User has just started this project."""

        self.persona.project.job_search_length_months = 1
        self.persona.project.job_search_started_at.FromDatetime(
            self.persona.project.created_at.ToDatetime() - datetime.timedelta(days=30.5))
        self._assert_pass_filter()

    def test_started_2_years_ago(self):
        """User has been working on this project for 2 years."""

        self.persona.project.job_search_length_months = 24
        self.persona.project.job_search_started_at.FromDatetime(
            self.persona.project.created_at.ToDatetime() - datetime.timedelta(days=732))
        self._assert_fail_filter()


class FilterUsingScoreTestCase(unittest.TestCase):
    """Unit tests for the filter_using_score function."""

    @classmethod
    def setUpClass(cls):
        """Test setup."""

        super(FilterUsingScoreTestCase, cls).setUpClass()
        scoring.SCORING_MODELS['test-zero'] = scoring.ConstantScoreModel(0)
        scoring.SCORING_MODELS['test-two'] = scoring.ConstantScoreModel(2)

    def test_filter_list_with_no_filters(self):
        """Filter a list with no filters to apply."""

        filtered = scoring.filter_using_score(range(5), lambda a: [], None)
        self.assertEqual([0, 1, 2, 3, 4], list(filtered))

    def test_filter_list_constant_scorer(self):
        """Filter a list returning constant scorer."""

        get_scoring_func = mock.MagicMock()
        get_scoring_func.side_effect = [['test-zero'], ['test-two'], ['test-zero']]
        filtered = scoring.filter_using_score(range(3), get_scoring_func, None)
        self.assertEqual([1], list(filtered))

    def test_unknown_filter(self):
        """Filter an item with an unknown filter."""

        get_scoring_func = mock.MagicMock()
        get_scoring_func.return_value = ['unknown-filter']
        filtered = scoring.filter_using_score([42], get_scoring_func, None)
        self.assertEqual([42], list(filtered))

    def test_multiple_filters(self):
        """Filter an item with multiple filters."""

        get_scoring_func = mock.MagicMock()
        get_scoring_func.return_value = ['test-two', 'test-zero']
        filtered = scoring.filter_using_score([42], get_scoring_func, None)
        self.assertEqual([], list(filtered))


class LBBFilterTestCase(FilterTestBase('for-recruiting-sector')):
    """Unit tests for the _LBBFilter class."""

    @mock.patch(companies.__name__ + '.get_lbb_companies')
    def test_big_company_recruiting(self, mock_get_lbb_companies):
        """Test that big companies return pass the filter."""

        mock_get_lbb_companies.return_value = iter([
            {'headcount_text': '0 salarié'},
            {'headcount_text': '500 à 999 salariés'},
        ])
        self._assert_pass_filter()

    @mock.patch(companies.__name__ + '.get_lbb_companies')
    def test_medium_companies_recruiting(self, mock_get_lbb_companies):
        """Test that multiple medium companies pass the filter."""

        mock_get_lbb_companies.return_value = iter([
            {'headcount_text': '250 à 499 salariés'},
            {'headcount_text': '250 à 499 salariés'},
        ])
        self._assert_pass_filter()

    @mock.patch(companies.__name__ + '.get_lbb_companies')
    def test_companies_not_recruiting(self, mock_get_lbb_companies):
        """Test that companies not recruiting does not pass the filter."""

        mock_get_lbb_companies.return_value = iter([
            {'headcount_text': '1 ou 2 salariés'},
            {'headcount_text': '1 ou 2 salariés'},
        ])
        self._assert_fail_filter()

    @mock.patch(companies.__name__ + '.get_lbb_companies')
    @mock.patch(companies.logging.__name__ + '.warning')
    def test_failed_lbb_response_parsing(self, mock_log_warning, mock_get_lbb_companies):
        """Test that companies not recruiting does not pass the filter."""

        mock_get_lbb_companies.return_value = iter([
            {'name': 'bad', 'headcount_text': 'moins de 10 salariés'},
            {'headcount_text': '990 ou 1990 salariés'},
        ])
        self._assert_pass_filter()
        mock_log_warning.assert_called()


class ContractTypeFilterTestCase(FilterTestBase('for-most-likely-short-contract')):
    """Unit tests for the _ContractTypeFilter class."""

    def test_recruiting_through_cdi(self):
        """Test that main contract CDI does not pass the filter."""

        self.database.job_group_info.insert_one({
            '_id': 'A1204',
            'requirements': {
                'contractTypes': [
                    {
                        'percentSuggested': 54,
                        'contractType': 'CDI',
                    },
                    {
                        'percentSuggested': 30,
                        'contractType': 'CDD_LESS_EQUAL_3_MONTHS',
                    },
                    {
                        'percentSuggested': 14,
                        'contractType': 'CDD_OVER_3_MONTHS',
                    },
                    {
                        'percentSuggested': 2,
                        'contractType': 'INTERIM',
                    }
                ]
            }
        })
        self.persona.project.target_job.job_group.rome_id = 'A1204'
        self._assert_fail_filter()

    def test_recruiting_through_cdd(self):
        """Test that main contract short CDD passes the filter."""

        self.database.job_group_info.insert_one({
            '_id': 'A1204',
            'requirements': {
                'contractTypes': [
                    {
                        'percentSuggested': 54,
                        'contractType': 'CDD_LESS_EQUAL_3_MONTHS',
                    },
                    {
                        'percentSuggested': 30,
                        'contractType': 'CDI',
                    },
                    {
                        'percentSuggested': 14,
                        'contractType': 'CDD_OVER_3_MONTHS',
                    },
                    {
                        'percentSuggested': 2,
                        'contractType': 'INTERIM',
                    }
                ]
            }
        })
        self.persona.project.target_job.job_group.rome_id = 'A1204'
        self._assert_pass_filter()

    def test_recruiting_through_cdds(self):
        """Test that compounded short contract are over 50% passes the filter."""

        self.database.job_group_info.insert_one({
            '_id': 'A1204',
            'requirements': {
                'contractTypes': [
                    {
                        'percentSuggested': 30,
                        'contractType': 'CDI',
                    },
                    {
                        'percentSuggested': 28,
                        'contractType': 'CDD_LESS_EQUAL_3_MONTHS',
                    },
                    {
                        'percentSuggested': 23,
                        'contractType': 'INTERIM',
                    },
                    {
                        'percentSuggested': 19,
                        'contractType': 'CDD_OVER_3_MONTHS',
                    }
                ]
            }
        })
        self.persona.project.target_job.job_group.rome_id = 'A1204'
        self._assert_pass_filter()


class OffersEvolutionFilterTestCase(FilterTestBase('for-evolution-of-offers(+10%)')):
    """Unit tests for the filter on evolution of offers."""

    def test_negative_evolution(self):
        """Test that a market which is not recruiting more than before fails the filter."""

        self.database.local_diagnosis.insert_one({
            '_id': '69:M1403',
            'job_offers_change': -5
        })
        self.persona.project.target_job.job_group.rome_id = 'M1403'
        self.persona.project.mobility.city.departement_id = '69'
        self._assert_fail_filter()

    def test_not_much_evolution(self):
        """Test that a market which is not recruiting much more than before fails the filter."""

        self.database.local_diagnosis.insert_one({
            '_id': '69:M1403',
            'job_offers_change': 5
        })
        self.persona.project.target_job.job_group.rome_id = 'M1403'
        self.persona.project.mobility.city.departement_id = '69'
        self._assert_fail_filter()

    def test_good_evolution(self):
        """Test that a market which is recruiting much more than before passes the filter."""

        self.database.local_diagnosis.insert_one({
            '_id': '69:M1403',
            'job_offers_change': 15
        })
        self.persona.project.target_job.job_group.rome_id = 'M1403'
        self.persona.project.mobility.city.departement_id = '69'
        self._assert_pass_filter()


if __name__ == '__main__':
    unittest.main()  # pragma: no cover
