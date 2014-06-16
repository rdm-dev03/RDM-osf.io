import httplib as http

from framework.exceptions import HTTPError
from website.addons.dataverse.dvn.connection import DvnConnection
from website.addons.dataverse import settings


def connect(username, password, host=settings.HOST):
    connection = DvnConnection(
        username=username,
        password=password,
        host=host,
        disable_ssl_certificate_validation=not settings.VERIFY_SSL,
    )
    return connection if connection.connected else None


def connect_from_settings(user_settings):
    return connect(
        user_settings.dataverse_username,
        user_settings.dataverse_password
    ) if user_settings else None


def connect_or_403(username, password, host=settings.HOST):
    connection = DvnConnection(
        username=username,
        password=password,
        host=host,
        disable_ssl_certificate_validation=not settings.VERIFY_SSL,
    )
    if connection.status == http.FORBIDDEN:
        raise HTTPError(http.FORBIDDEN)
    return connection if connection.connected else None


def connect_from_settings_or_403(user_settings):
    return connect_or_403(
        user_settings.dataverse_username,
        user_settings.dataverse_password
    ) if user_settings else None


def delete_file(file):
    study = file.hostStudy
    study.delete_file(file)


def upload_file(study, filename, content):
    study.add_file_obj(filename, content)


def get_file(study, filename, released=False):
    return study.get_file(filename, released)


def get_file_by_id(study, file_id, released=False):
    return study.get_file_by_id(file_id, released)


def get_files(study, released=False):
    return study.get_files(released)


def release_study(study):
    return study.release()


def get_studies(dataverse):
    if dataverse is None:
        return [], []
    accessible_studies = []
    bad_studies = []
    for s in dataverse.get_studies():
        try:
            if s.get_state() != 'DEACCESSIONED':
                accessible_studies.append(s)
        except UnicodeDecodeError:
            bad_studies.append(s)
    return accessible_studies, bad_studies


def get_study(dataverse, hdl):
    if dataverse is None:
        return
    study = dataverse.get_study_by_hdl(hdl)
    try:
        if study and study.get_state() != 'DEACCESSIONED':
            return study
    except UnicodeDecodeError:
        return None


def get_dataverses(connection):
    if connection is None:
        return []
    dataverses = connection.get_dataverses()
    released_dataverses = [d for d in dataverses if d.is_released]
    return released_dataverses


def get_dataverse(connection, alias):
    if connection is None:
        return
    dataverse = connection.get_dataverse(alias)
    return dataverse if dataverse and dataverse.is_released else None
