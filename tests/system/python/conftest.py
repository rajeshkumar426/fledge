# -*- coding: utf-8 -*-

# FLEDGE_BEGIN
# See: http://fledge.readthedocs.io/
# FLEDGE_END

""" Configuration system/python/conftest.py

"""
import subprocess
import os
import platform
import sys
import fnmatch
import http.client
import json
import base64
import ssl
import shutil
import pytest
from urllib.parse import quote

__author__ = "Vaibhav Singhal"
__copyright__ = "Copyright (c) 2019 Dianomic Systems"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"

sys.path.append(os.path.join(os.path.dirname(__file__), 'helpers'))
sys.path.append(os.path.join(os.path.dirname(__file__)))


@pytest.fixture
def clean_setup_fledge_packages(package_build_version):
    assert os.environ.get('FLEDGE_ROOT') is not None

    try:
        subprocess.run(["cd $FLEDGE_ROOT/tests/system/lab && ./remove"], shell=True, check=True)
    except subprocess.CalledProcessError:
        assert False, "remove package script failed!"

    try:
        subprocess.run(["$FLEDGE_ROOT/tests/system/python/scripts/package/setup {}".format(package_build_version)],
                       shell=True, check=True)
    except subprocess.CalledProcessError:
        assert False, "install package script failed"


@pytest.fixture
def reset_and_start_fledge(storage_plugin):
    """Fixture that kills fledge, reset database and starts fledge again
        storage_plugin: Fixture that defines the storage plugin to be used for tests
    """

    assert os.environ.get('FLEDGE_ROOT') is not None

    subprocess.run(["$FLEDGE_ROOT/scripts/fledge kill"], shell=True, check=True)
    if storage_plugin == 'postgres':
        subprocess.run(["sed -i 's/sqlite/postgres/g' $FLEDGE_ROOT/data/etc/storage.json"], shell=True, check=True)
    else:
        subprocess.run(["sed -i 's/postgres/sqlite/g' $FLEDGE_ROOT/data/etc/storage.json"], shell=True, check=True)

    subprocess.run(["echo YES | $FLEDGE_ROOT/scripts/fledge reset"], shell=True, check=True)
    subprocess.run(["$FLEDGE_ROOT/scripts/fledge start"], shell=True)
    stat = subprocess.run(["$FLEDGE_ROOT/scripts/fledge status"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert "Fledge not running." not in stat.stderr.decode("utf-8")


def find(pattern, path):
    result = None
    for root, dirs, files in os.walk(path):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                result = os.path.join(root, name)
    return result


@pytest.fixture
def remove_data_file():
    """Fixture that removes any file from a given path"""

    def _remove_data_file(file_path=None):
        if os.path.exists(file_path):
            os.remove(file_path)
    return _remove_data_file


@pytest.fixture
def remove_directories():
    """Fixture that recursively removes any file and directories from a given path"""

    def _remove_directories(dir_path=None):
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)
    return _remove_directories


@pytest.fixture
def add_south():
    def _add_fledge_south(south_plugin, south_branch, fledge_url, service_name="play", config=None,
                           plugin_lang="python", use_pip_cache=True, start_service=True, plugin_discovery_name=None,
                           installation_type='make'):
        """Add south plugin and start the service by default"""

        plugin_discovery_name = south_plugin if plugin_discovery_name is None else plugin_discovery_name
        _config = config if config is not None else {}
        _enabled = "true" if start_service else "false"
        data = {"name": "{}".format(service_name), "type": "South", "plugin": "{}".format(plugin_discovery_name),
                "enabled": _enabled, "config": _config}

        conn = http.client.HTTPConnection(fledge_url)

        def clone_make_install():
            try:
                if plugin_lang == "python":
                    subprocess.run(["$FLEDGE_ROOT/tests/system/python/scripts/install_python_plugin {} south {} {}".format(
                        south_branch, south_plugin, use_pip_cache)], shell=True, check=True)
                else:
                    subprocess.run(["$FLEDGE_ROOT/tests/system/python/scripts/install_c_plugin {} south {}".format(
                        south_branch, south_plugin)], shell=True, check=True)
            except subprocess.CalledProcessError:
                assert False, "{} plugin installation failed".format(south_plugin)

        if installation_type == 'make':
            clone_make_install()
        elif installation_type == 'package':
            try:
                os_platform = platform.platform()
                pkg_mgr = 'yum' if 'centos' in os_platform or 'redhat' in os_platform else 'apt'
                subprocess.run(["sudo {} install -y fledge-south-{}".format(pkg_mgr, south_plugin)], shell=True, check=True)
            except subprocess.CalledProcessError:
                assert False, "{} package installation failed!".format(south_plugin)
        else:
            print("Skipped {} plugin installation. Installation mechanism is set to {}.".format(south_plugin, installation_type))

        # Create south service
        conn.request("POST", '/fledge/service', json.dumps(data))
        r = conn.getresponse()
        assert 200 == r.status
        r = r.read().decode()
        retval = json.loads(r)
        assert service_name == retval["name"]
    return _add_fledge_south


@pytest.fixture
def start_north_pi_v2():
    def _start_north_pi_server_c(fledge_url, pi_host, pi_port, pi_token, north_plugin="PI_Server_V2",
                                 taskname="NorthReadingsToPI", start_task=True):
        """Start north task"""

        _enabled = "true" if start_task else "false"
        conn = http.client.HTTPConnection(fledge_url)
        data = {"name": taskname,
                "plugin": "{}".format(north_plugin),
                "type": "north",
                "schedule_type": 3,
                "schedule_day": 0,
                "schedule_time": 0,
                "schedule_repeat": 30,
                "schedule_enabled": _enabled,
                "config": {"producerToken": {"value": pi_token},
                           "URL": {"value": "https://{}:{}/ingress/messages".format(pi_host, pi_port)}
                           }
                }
        conn.request("POST", '/fledge/scheduled/task', json.dumps(data))
        r = conn.getresponse()
        assert 200 == r.status
        retval = r.read().decode()
        return retval
    return _start_north_pi_server_c


@pytest.fixture
def start_north_pi_v2_web_api():
    def _start_north_pi_server_c_web_api(fledge_url, pi_host, pi_port, pi_db="Dianomic", auth_method='basic',
                                         pi_user=None, pi_pwd=None, north_plugin="PI_Server_V2",
                                         taskname="NorthReadingsToPI_WebAPI", start_task=True):
        """Start north task"""

        _enabled = True if start_task else False
        conn = http.client.HTTPConnection(fledge_url)
        data = {"name": taskname,
                "plugin": "{}".format(north_plugin),
                "type": "north",
                "schedule_type": 3,
                "schedule_day": 0,
                "schedule_time": 0,
                "schedule_repeat": 10,
                "schedule_enabled": _enabled,
                "config": {"PIServerEndpoint": {"value": "PI Web API"},
                           "PIWebAPIAuthenticationMethod": {"value": auth_method},
                           "PIWebAPIUserId":  {"value": pi_user},
                           "PIWebAPIPassword": {"value": pi_pwd},
                           "URL": {"value": "https://{}:{}/piwebapi/omf".format(pi_host, pi_port)},
                           "compression": {"value": "true"}
                           }
                }

        conn.request("POST", '/fledge/scheduled/task', json.dumps(data))
        r = conn.getresponse()
        assert 200 == r.status
        retval = r.read().decode()
        return retval
    return _start_north_pi_server_c_web_api


start_north_pi_server_c = start_north_pi_v2
start_north_pi_server_c_web_api = start_north_pi_v2_web_api


@pytest.fixture
def read_data_from_pi():
    def _read_data_from_pi(host, admin, password, pi_database, asset, sensor):
        """ This method reads data from pi web api """

        # List of pi databases
        dbs = None
        # PI logical grouping of attributes and child elements
        elements = None
        # List of elements
        url_elements_list = None
        # Element's recorded data url
        url_recorded_data = None
        # Resources in the PI Web API are addressed by WebID, parameter used for deletion of element
        web_id = None

        username_password = "{}:{}".format(admin, password)
        username_password_b64 = base64.b64encode(username_password.encode('ascii')).decode("ascii")
        headers = {'Authorization': 'Basic %s' % username_password_b64}

        try:
            conn = http.client.HTTPSConnection(host, context=ssl._create_unverified_context())
            conn.request("GET", '/piwebapi/assetservers', headers=headers)
            res = conn.getresponse()
            r = json.loads(res.read().decode())
            dbs = r["Items"][0]["Links"]["Databases"]

            if dbs is not None:
                conn.request("GET", dbs, headers=headers)
                res = conn.getresponse()
                r = json.loads(res.read().decode())
                for el in r["Items"]:
                    if el["Name"] == pi_database:
                        elements = el["Links"]["Elements"]

            if elements is not None:
                conn.request("GET", elements, headers=headers)
                res = conn.getresponse()
                r = json.loads(res.read().decode())
                url_elements_list = r["Items"][0]["Links"]["Elements"]

            if url_elements_list is not None:
                conn.request("GET", url_elements_list, headers=headers)
                res = conn.getresponse()
                r = json.loads(res.read().decode())
                items = r["Items"]
                for el in items:
                    if el["Name"] == asset:
                        url_recorded_data = el["Links"]["RecordedData"]
                        web_id = el["WebId"]

            _data_pi = {}
            if url_recorded_data is not None:
                conn.request("GET", url_recorded_data, headers=headers)
                res = conn.getresponse()
                r = json.loads(res.read().decode())
                _items = r["Items"]
                for el in _items:
                    _recoded_value_list = []
                    for _head in sensor:
                        if el["Name"] == _head:
                            elx = el["Items"]
                            for _el in elx:
                                _recoded_value_list.append(_el["Value"])
                            _data_pi[_head] = _recoded_value_list

                # Delete recorded elements
                conn.request("DELETE", '/piwebapi/elements/{}'.format(web_id), headers=headers)
                res = conn.getresponse()
                res.read()

                return _data_pi
        except (KeyError, IndexError, Exception):
            return None
    return _read_data_from_pi


@pytest.fixture
def add_filter():
    def _add_filter(filter_plugin, filter_plugin_branch, filter_name, filter_config, fledge_url, filter_user_svc_task):
        """

        :param filter_plugin: filter plugin `fledge-filter-?`
        :param filter_plugin_branch:
        :param filter_name: name of the filter with which it will be added to pipeline
        :param filter_config:
        :param fledge_url:
        :param filter_user_svc_task: south service or north task instance name
        """

        try:
            subprocess.run(["$FLEDGE_ROOT/tests/system/python/scripts/install_c_plugin {} filter {}".format(
                filter_plugin_branch, filter_plugin)], shell=True, check=True)
        except subprocess.CalledProcessError:
            assert False, "{} filter plugin installation failed".format(filter_plugin)

        data = {"name": "{}".format(filter_name), "plugin": "{}".format(filter_plugin), "filter_config": filter_config}
        conn = http.client.HTTPConnection(fledge_url)

        conn.request("POST", '/fledge/filter', json.dumps(data))
        r = conn.getresponse()
        assert 200 == r.status
        r = r.read().decode()
        jdoc = json.loads(r)
        assert filter_name == jdoc["filter"]

        uri = "{}/pipeline?allow_duplicates=true&append_filter=true".format(quote(filter_user_svc_task))
        filters_in_pipeline = [filter_name]
        conn.request("PUT", '/fledge/filter/' + uri, json.dumps({"pipeline": filters_in_pipeline}))
        r = conn.getresponse()
        assert 200 == r.status
        res = r.read().decode()
        jdoc = json.loads(res)
        # Asset newly added filter exist in request's response
        assert filter_name in jdoc["result"]

    return _add_filter


@pytest.fixture
def enable_schedule():
    def _enable_sch(fledge_url, sch_name):
        conn = http.client.HTTPConnection(fledge_url)
        conn.request("PUT", '/fledge/schedule/enable', json.dumps({"schedule_name": sch_name}))
        r = conn.getresponse()
        assert 200 == r.status
        r = r.read().decode()
        jdoc = json.loads(r)
        assert "scheduleId" in jdoc

    return _enable_sch


@pytest.fixture
def disable_schedule():
    def _disable_sch(fledge_url, sch_name):
        conn = http.client.HTTPConnection(fledge_url)
        conn.request("PUT", '/fledge/schedule/disable', json.dumps({"schedule_name": sch_name}))
        r = conn.getresponse()
        assert 200 == r.status
        r = r.read().decode()
        jdoc = json.loads(r)
        assert jdoc["status"]

    return _disable_sch


def pytest_addoption(parser):
    parser.addoption("--storage-plugin", action="store", default="sqlite",
                     help="Database plugin to use for tests")
    parser.addoption("--fledge-url", action="store", default="localhost:8081",
                     help="Fledge client api url")
    parser.addoption("--use-pip-cache", action="store", default=False,
                     help="use pip cache is requirement is available")
    parser.addoption("--wait-time", action="store", default=5, type=int,
                     help="Generic wait time between processes to run")
    parser.addoption("--retries", action="store", default=3, type=int,
                     help="Number of tries for polling")
    # TODO: Temporary fixture, to be used with value False for environments where PI Web API is not stable
    parser.addoption("--skip-verify-north-interface", action="store_false",
                     help="Verify data from external north system api")

    parser.addoption("--remote-user", action="store", default="ubuntu",
                     help="Username on remote machine where Fledge will run")
    parser.addoption("--remote-ip", action="store", default="127.0.0.1",
                     help="IP of remote machine where Fledge will run")
    parser.addoption("--key-path", action="store", default="~/.ssh/id_rsa.pub",
                     help="Path of key file used for authentication to remote machine")
    parser.addoption("--remote-fledge-path", action="store",
                     help="Path on the remote machine where Fledge is clone and built")

    # South/North Args
    parser.addoption("--south-branch", action="store", default="develop",
                     help="south branch name")
    parser.addoption("--north-branch", action="store", default="develop",
                     help="north branch name")
    parser.addoption("--south-service-name", action="store", default="southSvc #1",
                     help="Name of the South Service")
    parser.addoption("--asset-name", action="store", default="SystemTest",
                     help="Name of asset")

    # Filter Args
    parser.addoption("--filter-branch", action="store", default="develop", help="Filter plugin repo branch")
    parser.addoption("--filter-name", action="store", default="Meta #1", help="Filter name to be added to pipeline")

    # External Services Arg fledge-service-* e.g. fledge-service-notification
    parser.addoption("--service-branch", action="store", default="develop",
                     help="service branch name")
    # Notify Arg
    parser.addoption("--notify-branch", action="store", default="develop", help="Notify plugin repo branch")

    # PI Config
    parser.addoption("--pi-host", action="store", default="pi-server",
                     help="PI Server Host Name/IP")
    parser.addoption("--pi-port", action="store", default="5460", type=int,
                     help="PI Server Port")
    parser.addoption("--pi-db", action="store", default="pi-server-db",
                     help="PI Server database")
    parser.addoption("--pi-admin", action="store", default="pi-server-uid",
                     help="PI Server user login")
    parser.addoption("--pi-passwd", action="store", default="pi-server-pwd",
                     help="PI Server user login password")
    parser.addoption("--pi-token", action="store", default="omf_north_0001",
                     help="OMF Producer Token")

    # OCS Config
    parser.addoption("--ocs-tenant", action="store", default="ocs_tenant_id",
                     help="Tenant id of OCS")
    parser.addoption("--ocs-client-id", action="store", default="ocs_client_id",
                     help="Client id of OCS account")
    parser.addoption("--ocs-client-secret", action="store", default="ocs_client_secret",
                     help="Client Secret of OCS account")
    parser.addoption("--ocs-namespace", action="store", default="ocs_namespace_0001",
                     help="OCS namespace where the information are stored")
    parser.addoption("--ocs-token", action="store", default="ocs_north_0001",
                     help="Token of OCS account")

    # Kafka Config
    parser.addoption("--kafka-host", action="store", default="localhost",
                     help="Kafka Server Host Name/IP")
    parser.addoption("--kafka-port", action="store", default="9092", type=int,
                     help="Kafka Server Port")
    parser.addoption("--kafka-topic", action="store", default="Fledge", help="Kafka topic")
    parser.addoption("--kafka-rest-port", action="store", default="8082", help="Kafka Rest Proxy Port")

    # Modbus Config
    parser.addoption("--modbus-host", action="store", default="localhost", help="Modbus simulator host")
    parser.addoption("--modbus-port", action="store", default="502", type=int, help="Modbus simulator port")
    parser.addoption("--modbus-serial-port", action="store", default="/dev/ttyS1", help="Modbus serial port")
    parser.addoption("--modbus-baudrate", action="store", default="9600", type=int, help="Serial port baudrate")

    # Packages
    parser.addoption("--package-build-version", action="store", default="nightly", help="Package build version for http://archives.dianomic.com")
    parser.addoption("--package-build-list", action="store", default="p0", help="Package to build as per key defined in tests/system/python/packages/data/package_list.json and comma separated values are accepted if more than one to build with")
    parser.addoption("--package-build-source-list", action="store", default="false", help="Package to build from apt/yum sources list")


@pytest.fixture
def storage_plugin(request):
    return request.config.getoption("--storage-plugin")


@pytest.fixture
def remote_user(request):
    return request.config.getoption("--remote-user")


@pytest.fixture
def remote_ip(request):
    return request.config.getoption("--remote-ip")


@pytest.fixture
def key_path(request):
    return request.config.getoption("--key-path")


@pytest.fixture
def remote_fledge_path(request):
    return request.config.getoption("--remote-fledge-path")


@pytest.fixture
def skip_verify_north_interface(request):
    return not request.config.getoption("--skip-verify-north-interface")


@pytest.fixture
def south_branch(request):
    return request.config.getoption("--south-branch")


@pytest.fixture
def north_branch(request):
    return request.config.getoption("--north-branch")


@pytest.fixture
def service_branch(request):
    return request.config.getoption("--service-branch")


@pytest.fixture
def filter_branch(request):
    return request.config.getoption("--filter-branch")


@pytest.fixture
def notify_branch(request):
    return request.config.getoption("--notify-branch")


@pytest.fixture
def use_pip_cache(request):
    return request.config.getoption("--use-pip-cache")


@pytest.fixture
def filter_name(request):
    return request.config.getoption("--filter-name")


@pytest.fixture
def south_service_name(request):
    return request.config.getoption("--south-service-name")


@pytest.fixture
def asset_name(request):
    return request.config.getoption("--asset-name")


@pytest.fixture
def fledge_url(request):
    return request.config.getoption("--fledge-url")


@pytest.fixture
def wait_time(request):
    return request.config.getoption("--wait-time")


@pytest.fixture
def retries(request):
    return request.config.getoption("--retries")


@pytest.fixture
def pi_host(request):
    return request.config.getoption("--pi-host")


@pytest.fixture
def pi_port(request):
    return request.config.getoption("--pi-port")


@pytest.fixture
def pi_db(request):
    return request.config.getoption("--pi-db")


@pytest.fixture
def pi_admin(request):
    return request.config.getoption("--pi-admin")


@pytest.fixture
def pi_passwd(request):
    return request.config.getoption("--pi-passwd")


@pytest.fixture
def pi_token(request):
    return request.config.getoption("--pi-token")


@pytest.fixture
def ocs_tenant(request):
    return request.config.getoption("--ocs-tenant")


@pytest.fixture
def ocs_client_id(request):
    return request.config.getoption("--ocs-client-id")


@pytest.fixture
def ocs_client_secret(request):
    return request.config.getoption("--ocs-client-secret")


@pytest.fixture
def ocs_namespace(request):
    return request.config.getoption("--ocs-namespace")


@pytest.fixture
def ocs_token(request):
    return request.config.getoption("--ocs-token")


@pytest.fixture
def kafka_host(request):
    return request.config.getoption("--kafka-host")


@pytest.fixture
def kafka_port(request):
    return request.config.getoption("--kafka-port")


@pytest.fixture
def kafka_topic(request):
    return request.config.getoption("--kafka-topic")


@pytest.fixture
def kafka_rest_port(request):
    return request.config.getoption("--kafka-rest-port")


@pytest.fixture
def modbus_host(request):
    return request.config.getoption("--modbus-host")


@pytest.fixture
def modbus_port(request):
    return request.config.getoption("--modbus-port")


@pytest.fixture
def modbus_serial_port(request):
    return request.config.getoption("--modbus-serial-port")


@pytest.fixture
def modbus_baudrate(request):
    return request.config.getoption("--modbus-baudrate")


@pytest.fixture
def package_build_version(request):
    return request.config.getoption("--package-build-version")


@pytest.fixture
def package_build_list(request):
    return request.config.getoption("--package-build-list")


@pytest.fixture
def package_build_source_list(request):
    return request.config.getoption("--package-build-source-list")


def pytest_itemcollected(item):
    par = item.parent.obj
    node = item.obj
    pref = par.__doc__.strip() if par.__doc__ else par.__class__.__name__
    suf = node.__doc__.strip() if node.__doc__ else node.__name__
    if pref or suf:
        item._nodeid = ' '.join((pref, suf))
