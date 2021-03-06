"""Importer for local job data mapped to ROME job groups to MongoDB.

The data will be imported into the `local_diagnosis` collection and follows
the structure of LocalJobStats from job.proto.

The data from this importer is indexed by `departement_id` and `rome_id` and
contains bmo, salaries and unemployment_duration.

You can try it out on a local instance:
 - Start your local environment with `docker-compose up frontend-dev`.
 - Run this script:
    docker-compose run --rm data-analysis-prepare \
        python bob_emploi/importer/local_diagnosis.py \
        --bmo_csv data/bmo/bmo_2015.csv \
        --fap_rome_crosswalk data/crosswalks/passage_fap2009_romev3.txt \
        --pcs_rome_crosswalk data/crosswalks/passage_pcs_romev3.csv \
        --salaries_csv data/fhs_salaries.csv \
        --unemployment_duration_csv data/fhs_category_a_duration.csv \
        --job_offers_changes_json data/job_offers/job_offers_changes.json \
        --imt_folder data/imt \
        --mongo_url mongodb://frontend-db/test
"""

import codecs
import itertools
import locale
from os import path

import numpy as np
import pandas

from bob_emploi.data_analysis.lib import cleaned_data
from bob_emploi.frontend.api import job_pb2
from bob_emploi.data_analysis.lib import mongo
from bob_emploi.data_analysis.lib import read_data

# Average number of days per month.
_DAYS_PER_MONTH = 30.5
_QUANTILES = {'min': 0.35, 'median': 0.5, 'max': 0.65}
locale.setlocale(locale.LC_ALL, 'fr_FR.UTF-8')

# Minimum number of jobseekers that is needed before we compute statistics.
_MIN_SALARY_COUNT = 15

# Denomiator to compute Market Score because the number of yearly average
# offers are given for 10 candidates.
_YEARLY_AVG_OFFERS_DENOMINATOR = 10

# Dictionary of proto fields for employment type.
_EMPLOYMENT_TYPE_PROTO_FIELDS = {
    1: job_pb2.CDI,
    2: job_pb2.CDD_LESS_EQUAL_3_MONTHS,
    3: job_pb2.CDD_OVER_3_MONTHS,
    4: job_pb2.INTERIM,
    99: job_pb2.UNDEFINED_EMPLOYMENT_TYPE,
}

# Dictionary of proto fields for salary unit.
_SALARY_UNIT_PROTO_FIELDS = {
    1: job_pb2.MONTHLY_GROSS_SALARY,
}
# Dictionary of proto fields for active months.
_ACTIVE_MONTHS_PROTO_FIELDS = {
    'UNK': job_pb2.UNKNOWN_MONTH,
    'SEASONAL_JAN': job_pb2.JANUARY,
    'SEASONAL_FEB': job_pb2.FEBRUARY,
    'SEASONAL_MAR': job_pb2.MARCH,
    'SEASONAL_APR': job_pb2.APRIL,
    'SEASONAL_MAY': job_pb2.MAY,
    'SEASONAL_JUNE': job_pb2.JUNE,
    'SEASONAL_JULY': job_pb2.JULY,
    'SEASONAL_AUG': job_pb2.AUGUST,
    'SEASONAL_SEP': job_pb2.SEPTEMBER,
    'SEASONAL_OCT': job_pb2.OCTOBER,
    'SEASONAL_NOV': job_pb2.NOVEMBER,
    'SEASONAL_DEC': job_pb2.DECEMBER,
}


def _isnan(value):
    """Check whether a Python value is numpy's NaN."""

    return isinstance(value, float) and np.isnan(value)


def _namedtuple_to_json_dict(item, fields, int_fields):
    for field in fields:
        value = getattr(item, field)
        if _isnan(value):
            continue
        # Pandas' itertuples treats column names starting with underscore
        # specially.
        if field == 'local_id':
            field = '_id'
        if field in int_fields:
            value = int(value)
        yield field, value


def csv2dicts(
        bmo_csv, fap_rome_crosswalk, pcs_rome_crosswalk, salaries_csv, unemployment_duration_csv,
        job_offers_changes_json, imt_folder, mobility_csv, data_folder='data'):
    """Import departement level diagnosis data in MongoDB.

    Args:
        bmo_csv: path to a CSV file containing the BMO data.
        fap_rome_crosswalk: path to the passage file from FAP to ROME codes.
        pcs_rome_crosswalk: path to the passage file from PCS to ROME codes.
        salaries_csv: path to the CSV file with FHS salaries.
        unemployment_duration_csv: path to the file with unemployment period
            durations. Can be generated by `make data/fhs_category_a_duration.csv`.
        job_offers_change_json: path to the file with job offers changes. Can be
            generated by `make data/job_offers/job_offers_changes.json`.
        mobility_csv: path to the ROME CSV file containing mobility between jobs
            and job groups.
        imt_folder: path to a local folder containing IMT csv files. Can be
            generated by `make imt`.
    """

    bmo_rome_data = _get_bmo_rome_data(bmo_csv, fap_rome_crosswalk)
    fhs_salaries = _get_fhs_salaries(salaries_csv)
    try:
        job_offers_changes = pandas.read_json(
            job_offers_changes_json, dtype={
                'jobOffersChange': int,
                'numJobOffersLastYear': int,
                'numJobOffersPreviousYear': int,
            })
    except ValueError:
        raise ValueError('Could not open the file "{}"'.format(job_offers_changes_json))
    job_offers_changes.rename(columns={'_id': 'local_id'}, inplace=True)
    unemployment_durations = _get_unemployment_durations(
        unemployment_duration_csv)
    market_score_csv = path.join(imt_folder, 'market_score.csv')
    market_score = _get_market_score(market_score_csv)
    employment_type_csv = path.join(imt_folder, 'employment_type.csv')
    employment_type = _get_employment_type_imt(employment_type_csv)
    imt_salaries_csv = path.join(imt_folder, 'salaries.csv')
    salaries = _get_salaries_imt(pcs_rome_crosswalk, imt_salaries_csv)
    imt_partial = pandas.merge(market_score, employment_type, on='local_id', how='outer')
    imt_full = pandas.merge(imt_partial, salaries, on='local_id', how='outer')
    imt_full = _clean_empty_fields_imt(imt_full)
    imt = pandas.DataFrame()
    imt['local_id'] = imt_full.local_id
    imt_full = imt_full[imt_full.columns.difference(['local_id'])]
    imt['imt'] = imt_full.apply(lambda x: x.to_dict(), axis='columns')
    less_stressful = _get_less_stressful_job_groups(data_folder, mobility_csv, market_score_csv)
    local_diagnosis = pandas.merge(
        bmo_rome_data, fhs_salaries, on='local_id', how='outer')
    local_diagnosis = pandas.merge(
        local_diagnosis, unemployment_durations, on='local_id', how='outer')
    local_diagnosis = pandas.merge(
        local_diagnosis, job_offers_changes, on='local_id', how='outer')
    local_diagnosis = pandas.merge(
        local_diagnosis, imt, on='local_id', how='outer')
    local_diagnosis = pandas.merge(
        local_diagnosis, less_stressful, on='local_id', how='outer')
    int_columns = (set(job_offers_changes.columns) - set(['local_id']))
    return [
        dict(_namedtuple_to_json_dict(item, [
            'local_id', 'bmo', 'salary', 'imt', 'lessStressfulJobGroups',
            # TODO: Consider removing this one now that we have the more
            # precise one (per city).
            'unemploymentDuration',
            'jobOffersChange', 'numJobOffersLastYear',
            'numJobOffersPreviousYear'], int_columns))
        for item in local_diagnosis.itertuples()]


def _clean_empty_fields_imt(imt_dataframe):
    """Replace NAN with default values in IMT.
    Because IMT data comes from various sources there may be some fields missing
    while others are present. Thus we replace the missing values with default values.

    Args:
        imt_dataframe: A dataframe with IMT data, columns correspond to IMT fields.

    Returns: A dataframe with some fields set to default values.

    """

    df_filled = imt_dataframe
    default_values = {
        'lastWeekDemand': 0,
        'lastWeekOffers': 0,
        'seasonal': False,
        'yearlyAvgOffersDenominator': 0,
        'yearlyAvgOffersPer10Candidates': 0}
    df_filled.fillna(value=default_values, inplace=True)
    for field in ['activeMonths', 'employmentTypePercentages']:
        df_filled[field] = df_filled[field]\
            .apply(lambda d: d if isinstance(d, list) else [])
    for field in ['juniorSalary', 'seniorSalary']:
        df_filled[field] = df_filled[field]\
            .apply(lambda d: d if isinstance(d, dict) else {})
    return df_filled


def _get_unemployment_durations(unemployment_duration_csv):
    """Get a very simple unemployment duration estimate from FHS data.

    We tried to built a more complex model but did not come to a satisfying
    solution. That's why we decided to simply compute the median for now.

    Args:
        unemployment_duration_csv: A file created via fhs_category_duration.py.
            See Makefile for examples of how to run it.

    Returns: A dataframe with `local_id` and one column with
        unemployment_duration objects that fit the DurationEstimation proto.
    """

    last_periods = pandas.read_csv(
        unemployment_duration_csv, dtype={'city_id': str})
    last_periods['departement_id'] = last_periods.city_id.str[:2]
    # Oversee départements are 3 digits long.
    last_periods.loc[last_periods.departement_id == '97', 'departement_id'] = (
        last_periods.city_id.str[:3])
    group_cols = ['code_rome', 'departement_id']
    unemployment_durations = last_periods.groupby(
        group_cols).duration.median().reset_index()
    local_id = unemployment_durations.departement_id.str.cat(
        unemployment_durations.code_rome, sep=':')
    return pandas.DataFrame({
        'unemploymentDuration': [
            {'days': int(item.duration)} for item in unemployment_durations.itertuples()],
        'local_id': local_id
    })


def _get_bmo_rome_data(bmo_csv, fap_rome_crosswalk):
    """Extract BMO information from a CSV.

    Currently this is pretty hacky: the BMO is defined for each
    "Bassin d'emploi" and each "Métier" as a FAP code, but our application
    relies on "département" and ROME code.

    We aggregate the data at the département level.

    HACK: Each FAP is mapped to a ROME ID, if a FAP maps to several ROME IDs
    we just pick one of them and if several FAPs map to the same ROME ID we
    just pick one of those.
    # TODO: Keep it as FAP and have our application find the user's FAP.

    Args:
      bmo_csv: path to a CSV file containing the BMO data.
      fap_rome_crosswalk: path to the passage file from FAP to ROME codes.
    """

    with codecs.open(fap_rome_crosswalk, 'r', 'latin-1') as fap_rome_file:
        fap_rome = read_data.parse_fap_rome_crosswalk(fap_rome_file.readlines())
    # As mentionned in the function's doc, this is not optimal.
    fap_rome.rome = fap_rome.rome.str[:5]
    fap_rome.drop_duplicates('fap', inplace=True)
    fap_to_rome = fap_rome.set_index('fap').rome

    bmo = pandas.read_csv(bmo_csv, dtype={
        'DEPARTEMENT_CODE': str,
        'REGION_CODE': str,
    }).fillna(0)
    bmo.rename(columns={
        'DEPARTEMENT_CODE': 'departement_id',
        'FAP_CODE': 'fap',
        'NB_RECRUT_PROJECTS': 'hiring_planned',
        'NB_SEASON_RECRUT_PROJECTS': 'seasonal_hiring_planned',
        'NB_DIFF_RECRUT_PROJECTS': 'difficult_hiring_planned',
    }, inplace=True)
    bmo['rome_id'] = bmo.fap.map(fap_to_rome)

    # Sum up data by département (because it's based on bassins d'emploi).
    # TODO: Get the user's bassin d'emploi and stop grouping it.
    bmo_rome = bmo.groupby(
        ['rome_id', 'departement_id'], sort=False, as_index=False).sum()
    bmo_rome['percentSeasonal'] = (
        bmo_rome.seasonal_hiring_planned * 100 /
        bmo_rome.hiring_planned).round().astype(int)
    bmo_rome['percentDifficult'] = (
        bmo_rome.difficult_hiring_planned * 100 /
        bmo_rome.hiring_planned).round().astype(int)
    return pandas.DataFrame({
        'bmo': [{
            'percentSeasonal': int(item.percentSeasonal),
            'percentDifficult': int(item.percentDifficult),
        } for item in bmo_rome.itertuples()],
        'local_id': bmo_rome.departement_id.str.cat(bmo_rome.rome_id, sep=':')
    })


def _get_fhs_salaries(salaries_csv):
    """Get salary estimates from FHS dataset.

    Args:
        salaries_csv: path to a CSV file prepared by the fhs_salaries script.

    Returns:
        A dataframe with a `local_id` added for joining to other datasets.
    """

    # See http://go/pe:notebooks/datasets/FHS_salaries.ipynb
    salaries = pandas.read_csv(salaries_csv, dtype={'departement_id': str})
    # TODO: Make a better filter or clean up the data.
    salaries = salaries[
        (salaries.salary_high > 1000) & (salaries.salary_high < 100000)]\
        .sort_values('salary_high')
    # TODO: Fallback on nation-wide stats.
    salaries_groups = salaries.groupby(
        ['departement_id', 'code_rome'], sort=False, group_keys=False)
    fhs_salaries = salaries_groups.apply(
        _salaries_diagnosis).dropna().to_frame(name='salary').reset_index()
    fhs_salaries['local_id'] = fhs_salaries.departement_id.str.cat(
        fhs_salaries.code_rome, sep=':')
    return fhs_salaries[['local_id', 'salary']]


def _salaries_diagnosis(salaries):
    total_count = salaries['count'].sum()
    if total_count < _MIN_SALARY_COUNT:
        return None
    cumulative_count = salaries['count'].cumsum()
    estimation = {}
    for name, quantile in _QUANTILES.items():
        quantile_salaries = salaries[cumulative_count <= quantile * total_count]
        if not quantile_salaries.empty:
            salary = float(quantile_salaries.salary_high.max())
        else:
            min_salary = float(salaries.salary_low.min())
            max_salary = float(salaries.salary_high.max())
            # All the job seekers are in the same bucket and we lost the
            # precise info about what is the distribution. We just assume an
            # even distribution inside the whole range.
            salary = min_salary * (1 - quantile) + quantile * max_salary
        estimation['{}Salary'.format(name)] = salary
    return finalize_salary_estimation(estimation)


def _get_less_stressful_job_groups(data_folder, mobility_csv, market_score_csv):
    mobility = cleaned_data.rome_job_groups_mobility(data_folder, filename=mobility_csv)
    market_stats = pandas.read_csv(market_score_csv, dtype={'AREA_CODE': 'str'})
    market_stats['departement_id'] = market_stats.AREA_CODE
    market_stats['market_score'] = market_stats.TENSION_RATIO.div(_YEARLY_AVG_OFFERS_DENOMINATOR)
    market_stats['yearlyAvgOffersPer10Candidates'] = market_stats.TENSION_RATIO
    market_stats['code_rome'] = market_stats.ROME_PROFESSION_CARD_CODE
    market_stats['yearlyAvgOffersDenominator'] = _YEARLY_AVG_OFFERS_DENOMINATOR
    market_stats = market_stats.set_index(['code_rome', 'departement_id'])
    market_stats.dropna(subset=['market_score'], inplace=True)
    market_stats_dept = market_stats[market_stats.AREA_TYPE_CODE == 'D']

    # Extend ROME mobility with IMT market scores.
    scored_mobility = mobility.merge(
        market_stats_dept.market_score.reset_index(),
        left_on='source_rome_id',
        right_on='code_rome')
    scored_mobility = scored_mobility.join(
        market_stats_dept,
        on=['target_rome_id', 'departement_id'],
        how='inner',
        lsuffix='_source')

    # Keep only the 5 best reorientations per market.
    best_reorientations = scored_mobility[
        scored_mobility.market_score >= 1.5 * scored_mobility.market_score_source]\
        .sort_values('market_score', ascending=False)\
        .groupby(['code_rome', 'departement_id'])\
        .apply(lambda x: x[:5].to_dict(orient='records'))\
        .to_frame('orientations').reset_index()

    return pandas.DataFrame([
        {
            'local_id': '{}:{}'.format(r.departement_id, r.code_rome),
            'lessStressfulJobGroups': [{
                'jobGroup': {'romeId': o['target_rome_id'], 'name': o['target_rome_name']},
                'mobilityType': o['mobility_type'],
                'localStats': {
                    'imt': {
                        'yearlyAvgOffersPer10Candidates': o['yearlyAvgOffersPer10Candidates'],
                        'yearlyAvgOffersDenominator': o['yearlyAvgOffersDenominator']
                    },
                },
            } for o in r.orientations],
        }
        for unused_index, r in best_reorientations.iterrows()])


def _get_market_score(market_score_csv):
    market_stats = pandas.read_csv(market_score_csv, dtype={'AREA_CODE': 'str'})
    seasonal_stats = market_stats[[
        column for column in market_stats.columns if column.startswith('SEASONAL_')]]
    seasonality_months = seasonal_stats.apply(_get_active_months, axis='columns', reduce=True)
    market_stats['seasonality'] = seasonality_months.seasonality

    # Converting to int from np.int32 so that json serialization does not choke.
    market_stats['yearlyAvgOffersPer10Candidates'] = pandas.to_numeric(
        market_stats.TENSION_RATIO)
    market_stats['lastWeekOffers'] = pandas.to_numeric(market_stats.NB_OFFER_LAST_WEEK)
    market_stats['lastWeekDemand'] = pandas.to_numeric(market_stats.NB_APPLICATION_LAST_WEEK)
    market_stats['seasonal'] = market_stats.SEASONAL == 'O'
    market_stats['activeMonths'] = market_stats.seasonality
    market_stats['local_id'] = market_stats.AREA_CODE + ':' \
        + market_stats.ROME_PROFESSION_CARD_CODE
    # TODO(pascal): Clean up this field.
    market_stats['yearlyAvgOffersDenominator'] = 10
    market_stats_dept = market_stats[market_stats.AREA_TYPE_CODE == 'D']
    return market_stats_dept[[
        'local_id', 'yearlyAvgOffersPer10Candidates', 'lastWeekOffers',
        'lastWeekDemand', 'seasonal', 'activeMonths', 'yearlyAvgOffersDenominator']]


def _get_active_months(seasonal_stats):
    """For a given market (job x area), get months in which hiring is stronger than in others.

        Args:
            seasonal_stats: dataframe is months in column and 'O' ('yes') or 'N' ('no') stating if
            the months is seasonal or not.

        Returns:
            list of active months.
    """

    months = seasonal_stats.index
    is_active = [month == 'O' for month in seasonal_stats]
    active_months = list(itertools.compress(months, is_active))
    seasonal_stats['seasonality'] = [
        job_pb2.Month.Name(_ACTIVE_MONTHS_PROTO_FIELDS[month]) for month in active_months]
    return seasonal_stats


def _get_employment_type_imt(employment_type_csv):
    employment_types = pandas.read_csv(employment_type_csv, dtype={'AREA_CODE': 'str'})
    employment_types_dept = employment_types[
        employment_types.AREA_TYPE_CODE == 'D']
    employment_percentages = employment_types_dept\
        .groupby(['ROME_PROFESSION_CARD_CODE', 'AREA_CODE', 'AREA_TYPE_CODE'])\
        .apply(_get_employment_type_perc)\
        .to_frame('employmentTypePercentages')
    employment_percentages = employment_percentages.reset_index()
    employment_percentages['local_id'] = employment_percentages.AREA_CODE \
        + ':' + employment_percentages.ROME_PROFESSION_CARD_CODE
    return employment_percentages[['local_id', 'employmentTypePercentages']]


def _get_employment_type_perc(market):
    return [{
        'employmentType': job_pb2.EmploymentType.Name(
            _EMPLOYMENT_TYPE_PROTO_FIELDS[row.CONTRACT_TYPE_CODE]),
        'percentage': row.OFFERS_PERCENT} for row in market.itertuples()]


def _get_salaries_imt(pcs_rome_crosswalk, imt_salaries_csv):
    """Get IMT data with salary info from imt_salaries_csv.

    Args:
        pcs_rome_crosswalk: path to a TXT file with PCS to ROME mapping.
        imt_salaries_csv: path to a CSV file with salaries retrieved from Emploi
            Store Dev API. Can be generated by `make data/imt/salaries.csv`.

    Returns:
        A dataframe with IMT salaries data.
    """

    pcs_rome = pandas.read_csv(pcs_rome_crosswalk)
    salaries = pandas.read_csv(imt_salaries_csv, dtype={'AREA_CODE': 'str'})
    salaries_dept = salaries[
        (salaries.AREA_TYPE_CODE == 'D') & (salaries.MINIMUM_SALARY > 0)]
    salaries_dept = salaries_dept.merge(
        pcs_rome, how='inner', left_on='PCS_PROFESSION_CODE', right_on='PCS')
    salaries_dept['local_id'] = salaries_dept.AREA_CODE + ':' + salaries_dept.ROME

    minimum_salary = salaries_dept.groupby(['local_id', 'AGE_GROUP_CODE']).MINIMUM_SALARY.min()
    maximum_salary = salaries_dept.groupby(['local_id', 'AGE_GROUP_CODE']).MAXIMUM_SALARY.max()

    salary_indexed = salaries_dept.set_index(['local_id', 'AGE_GROUP_CODE'])
    salary_indexed['pcs_min_salary'] = minimum_salary
    salary_indexed['pcs_max_salary'] = maximum_salary
    salaries_updated = salary_indexed.reset_index().set_index('local_id')
    salaries_updated = salaries_updated.drop_duplicates(['AGE_GROUP_CODE', 'ROME', 'AREA_CODE'])
    salaries_updated['seniority'] = salaries_updated.AGE_GROUP_CODE.map({1: 'junior', 2: 'senior'})

    pivot = salaries_updated.reset_index().pivot(index='local_id', columns='seniority')

    salaries_updated[[
        'junior_min_salaries', 'senior_min_salaries',
        'junior_max_salaries', 'senior_max_salaries']] = pivot[['pcs_min_salary', 'pcs_max_salary']]

    salaries_updated['juniorSalary'] = salaries_updated.apply(
        lambda x: _get_single_salary_detail(
            x.loc['junior_min_salaries'], x.loc['junior_max_salaries']), axis='columns')
    salaries_updated['seniorSalary'] = salaries_updated.apply(
        lambda x: _get_single_salary_detail(
            x.loc['senior_min_salaries'], x.loc['senior_max_salaries']), axis='columns')
    # Because of multiple PCS can map to the same ROME, we may have duplicated rows.
    # Here we will keep only the first one.
    return salaries_updated.reset_index()[[
        'juniorSalary', 'seniorSalary', 'local_id']].drop_duplicates('local_id')


def _get_salaries_details(market):
    return {
        'juniorSalary': _get_single_salary_detail(
            market.junior_min_salaries, market.junior_max_salaries),
        'seniorSalary': _get_single_salary_detail(
            market.senior_min_salaries, market.senior_max_salaries)
    }


def _get_single_salary_detail(min_salary, max_salary):
    salary_unit = job_pb2.SalaryUnit.Name(_SALARY_UNIT_PROTO_FIELDS[1])
    short_text = 'De {}€ à {}€'.format(min_salary, max_salary)
    return {
        'unit': salary_unit,
        'shortText': short_text,
        'minSalary': min_salary,
        'maxSalary': max_salary
    }


def finalize_salary_estimation(estimation):
    """Finalize the data for a SalaryEstimation proto.

    Args:
        estimation: a dict with min/max/medianSalary. This dict will be
            modified.

    Returns:
        The input dict with additional fields to be displayed.
    """

    estimation['shortText'] = '{} - {}'.format(
        locale.format('%d', estimation['minSalary'], grouping=True),
        locale.format('%d', estimation['maxSalary'], grouping=True))
    estimation['unit'] = 'ANNUAL_GROSS_SALARY'
    return estimation


if __name__ == '__main__':
    mongo.importer_main(csv2dicts, 'local_diagnosis')  # pragma: no cover
