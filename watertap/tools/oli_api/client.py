###############################################################################
# WaterTAP Copyright (c) 2020-2023, The Regents of the University of California,
# through Lawrence Berkeley National Laboratory, Oak Ridge National Laboratory,
# National Renewable Energy Laboratory, and National Energy Technology
# Laboratory (subject to receipt of any required approvals from the U.S. Dept.
# of Energy). All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and license
# information, respectively. These files are also available online at the URL
# "https://github.com/watertap-org/watertap/"
#
# OLI Systems, Inc. Copyright © 2022, all rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation and/or
# other materials provided with the distribution.
#
# 3. Neither the name of OLI Systems, Inc. nor the names of any contributors to
# the software made available herein may be used to endorse or promote products derived
# from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT
# SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT
# OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
# TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# You are under no obligation whatsoever to provide any bug fixes, patches, or upgrades to the
# features, functionality or performance of the source code ("Enhancements") to anyone; however,
# if you choose to make your Enhancements available either publicly, or directly to OLI Systems, Inc.,
# without imposing a separate written license agreement for such Enhancements, then you hereby grant
# the following license: a non-exclusive, royalty-free perpetual license to install, use, modify, prepare
# derivative works, incorporate into other computer software, distribute, and sublicense such enhancements
# or derivative works thereof, in binary and source code form.
###############################################################################

__author__ = "Adam Atia, Adi Bannady, Paul Vecchiarelli"

import logging
from pyomo.common.dependencies import attempt_import
asyncio, asyncio_available = attempt_import("asyncio", defer_check=False)

import random

import sys
import requests
import json
import time
import copy

from watertap.tools.oli_api.util.chemistry_helper_functions import get_oli_name

_logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    "OLIAPI - %(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"
)
handler.setFormatter(formatter)
_logger.addHandler(handler)
_logger.setLevel(logging.DEBUG)

class OLIApi:
    """
    A class to wrap OLI Cloud API calls and access functions for interfacing with WaterTAP.
    """

    def __init__(self, credential_manager, debug_level="INFO", interactive_mode=True):
        """
        Construct all necessary attributes for OLIApi class.

        :param credential_manager_class: class used to manage credentials
        :param debug_level: string defining level of logging activity
        :param interactive_mode: boolean enabling user interaction via prompts
        """

        self.credential_manager = credential_manager
        self.interactive_mode = interactive_mode
        if self.interactive_mode:
            _logger.info(
                "OLI running in interactive mode, disable with 'interactive_mode=False'"
            )
        if debug_level == "INFO":
            _logger.setLevel(logging.INFO)
        else:
            _logger.setLevel(logging.DEBUG)

    # binds OLIApi instance to context manager
    def __enter__(self):
        self.session_dbs_files = []
        return self

    # return False if no exceptions raised
    def __exit__(self, exc_type=None, exc_value=None, traceback=None):
        # delete all .dbs files created during session
        self.dbs_file_cleanup(self.session_dbs_files)
        return False

    def _prompt(self, msg, default=""):
        if self.interactive_mode:
            return input(msg)
        else:
            _logger.info(msg)
            return default

    def upload_dbs_file(self, dbs_file_path, keep_file=False):
        """
        Upload a DBS file to OLI Cloud given a full file path.

        :param dbs_file_path: string path to DBS file
        :param keep_file: bool to remove (default) or ignore DBS file during session cleanup

        :return dbs_file_id: string name for DBS file ID
        """

        with open(dbs_file_path, "rb") as file:
            req = requests.post(
                self.credential_manager.upload_dbs_url,
                headers=self.credential_manager.headers,
                files={"files": file},
            )
        dbs_file_id = self._request_status_test(req, ["UPLOADED"])["file"][0]["id"]
        if bool(dbs_file_id):
            if not keep_file:
                self.session_dbs_files.append(dbs_file_id)
            _logger.info(f"DBS file ID is {dbs_file_id}")
            return dbs_file_id
        else:
            raise RuntimeError("Unexpected failure getting DBS file ID.")

    def generate_dbs_file(
        self,
        inflows,
        thermo_framework=None,
        model_name=None,
        phases=None,
        databanks=None,
        keep_file=False,
    ):
        """
        Generate a DBS file on OLI Cloud given chemistry inputs.

        :param inflows: dictionary with inflows and optional custom parameters
        :param thermo_framework: string name of thermodynamic databank to use
        :param model_name: string name of model OLI will use
        :param phases: container dict for chemistry model parameters
        :param databanks: list of databanks to include in DBS file
        :param keep_file: bool to remove (default) or ignore DBS file during session cleanup

        :return dbs_file_id: string name for DBS file ID
        """

        dbs_file_inputs = {
            "thermodynamicFramework": None,
            "modelName": None,
            "phases": None,
            "inflows": None,
            "privateDatabanks": None,
        }

        if not inflows:
            raise RuntimeError("Inflows must be defined for Water Analysis.")
        solute_list = [{"name": get_oli_name(k)} for k in inflows]
        if not solute_list:
            raise RuntimeError("No inflows extracted from {inflows}.")
        dbs_file_inputs["inflows"] = solute_list

        if thermo_framework is not None:
            if thermo_framework in ["MSE (H3O+ ion)", "Aqueous (H+ ion)"]:
                dbs_file_inputs["thermodynamicFramework"] = thermo_framework
            else:
                raise RuntimeError(
                    "Failed DBS file generation. "
                    + f"Unexpected thermo_framework: {thermo_framework}."
                )
        else:
            dbs_file_inputs["thermodynamicFramework"] = "MSE (H3O+ ion)"

        if model_name is not None:
            dbs_file_inputs["modelName"] = str(model_name)
        else:
            dbs_file_inputs["modelName"] = "OLI_analysis"

        valid_phases = ["liquid1", "vapor", "solid", "liquid2"]
        if phases is not None:
            invalid_phases = [p for p in phases if p not in valid_phases]
            if invalid_phases:
                raise RuntimeError(
                    "Failed DBS file generation. "
                    + f"Unexpected phase(s): {invalid_phases}"
                )
            dbs_file_inputs["phases"] = phases
        else:
            dbs_file_inputs["phases"] = ["liquid1", "solid"]

        valid_databanks = ["XSC"]
        if databanks is not None:
            invalid_databanks = [db for db in databanks if db not in valid_databanks]
            if invalid_databanks:
                raise RuntimeError(
                    "Failed DBS file generation. "
                    + f"Unexpected databanks(s): {invalid_databanks}"
                )
            dbs_file_inputs["privateDatabanks"] = databanks

        dbs_dict = {
            "method": "chemistrybuilder.generateDBS",
            "params": {k: v for k, v in dbs_file_inputs.items() if v is not None},
        }
        _logger.debug(f"DBS input dictionary: {dbs_dict}")
        req = requests.post(
            self.credential_manager.dbs_url,
            headers=self.credential_manager.update_headers(
                {"Content-Type": "application/json"}
            ),
            data=json.dumps(dbs_dict),
        )
        dbs_file_id = self._request_status_test(req, ["SUCCESS"])["data"]["id"]
        if bool(dbs_file_id):
            if not keep_file:
                self.session_dbs_files.append(dbs_file_id)
            _logger.info(f"DBS file ID is {dbs_file_id}")
            return dbs_file_id
        else:
            raise RuntimeError("Unexpected failure getting DBS file ID.")

    def get_dbs_file_summary(self, dbs_file_id):
        """
        Get chemistry info and flash history for a DBS file.

        :param dbs_file_id: string name for DBS file ID

        :return dbs_file_summary: dictionary containing JSON results from OLI Cloud
        """

        _logger.info(f"Getting summary for {dbs_file_id} ...")
        chemistry_info = self.call("chemistry-info", dbs_file_id)
        req_flash_hist = requests.get(
            f"{self.credential_manager.engine_url}/flash/history/{dbs_file_id}",
            headers=self.credential_manager.headers,
        )
        flash_history = self._request_status_test(req_flash_hist, None)["data"]
        dbs_file_summary = {
            "chemistry_info": chemistry_info,
            "flash_history": flash_history,
        }
        missing_keys = [k for k, v in dbs_file_summary.items() if not v]
        if len(missing_keys) > 0:
            raise RuntimeError(
                " Failed to create DBS file summary. " + f"Missing {missing_keys}."
            )
        _logger.info(f"Completed DBS file summarization")
        return dbs_file_summary

    def get_user_dbs_file_ids(self):
        """
        Get all DBS files on user's cloud.

        :return user_dbs_file_ids: list of user DBS files saved on OLI Cloud
        """

        _logger.info("Getting DBS file IDs for user ...")
        req = requests.get(
            self.credential_manager.dbs_url,
            headers=self.credential_manager.headers,
        )
        user_dbs_file_ids = [
            k["fileId"] for k in self._request_status_test(req, None)["data"]
        ]
        _logger.info(f"{len(user_dbs_file_ids)} DBS files found for user")
        return user_dbs_file_ids

    def dbs_file_cleanup(self, dbs_file_ids=None):
        """
        Delete all (or specified) DBS files on OLI Cloud.

        :param dbs_file_ids: list of DBS file IDs to delete
        """

        if dbs_file_ids is None:
            dbs_file_ids = self.get_user_dbs_file_ids()
        r = self._prompt(
            f"WaterTAP will delete {len(dbs_file_ids)} DBS files [y]/n ", "y"
        )
        if (r.lower() == "y") or (r == ""):
            for dbs_file_id in dbs_file_ids:
                _logger.info(f"Deleting {dbs_file_id} ...")
                req = requests.request(
                    "DELETE",
                    f"{self.credential_manager._delete_dbs_url}/{dbs_file_id}",
                    headers=self.credential_manager.headers,
                )
                req = self._request_status_test(req, ["SUCCESS"])
                if req["status"] == "SUCCESS":
                    _logger.info(f"File deleted")

    def _get_flash_mode(self, dbs_file_id, flash_method, burst_job_tag=None):
        """
        Set up arguments for OLI requests.

        :param dbs_file_id: string name for DBS file ID
        :param flash_method: string indicating flash method

        """

        if not bool(flash_method):
            raise IOError("Specify a flash method to run.")
        if not bool(dbs_file_id):
            raise IOError("Specify a DBS file ID to flash.")

        headers = self.credential_manager.headers
        base_url = self.credential_manager.engine_url
        valid_get_flashes = ["corrosion-contact-surface", "chemistry-info"]
        valid_post_flashes = ["isothermal", "corrosion-rates", "wateranalysis"]
        if flash_method in valid_get_flashes:
            mode = "GET"
            url = f"{base_url}/file/{dbs_file_id}/{flash_method}"
        elif flash_method in valid_post_flashes:
            mode = "POST"
            url = f"{base_url}/flash/{dbs_file_id}/{flash_method}"
            headers = self.credential_manager.update_headers(
                {"Content-Type": "application/json"},
            )
            if burst_job_tag is not None:
                url = "{}?{}".format(
                    url, "burst={}_{}".format("watertap_burst", burst_job_tag)
                )
        else:
            valid_flashes = [*valid_get_flashes, *valid_post_flashes]
            raise RuntimeError(
                f" Unexpected value for flash_method: {flash_method}. "
                + "Valid values: {', '.join(valid_flashes)}."
            )
        return mode, url, headers

    def process_request_list(self, requests, batch_size=None, burst_job_tag=None):
        """
        Process a list of OLI requests.

        :param requests: list of dictionaries for OLI calls
        :param burst_job_tag: integer applied to OLI urls to leverage burst

        :return result_list: list of JSON results from OLI
        """

        #if burst_job_tag is None:
        #    burst_job_tag = random.randint(0, 100000)

        # generate batches of call coroutines
        def batch_generator(requests, batch_size):
            num_requests = len(requests)
            if not batch_size or batch_size > len(requests):
                batch_size = num_requests
                num_batches = 1
                label = "batch"
            else:
                num_batches = int(num_requests / batch_size)
                if num_requests % batch_size:
                    num_batches += 1
                if num_batches > 1:
                    label = "batches"
            _logger.info(f"Submitting {num_requests} requests as {num_batches} {label} ... ")
            requests_batched = []
            for batch in range(num_batches):
                bounds = (batch*batch_size, (batch+1)*batch_size)
                yield call_generator(requests, bounds)
                if bounds[1] >= len(requests):
                    break

        # generate call coroutines
        def call_generator(requests, bounds):
            for idx, request in enumerate(requests[bounds[0]:bounds[1]]):
                yield self.call_async(
                    **request,
                    burst_job_tag=burst_job_tag,
                    index=bounds[0]+idx,
                )

        # send call coroutines and await results
        async def collect_results(requests, batch_size):
            result_list = []
            for batch in batch_generator(requests, batch_size):
                await asyncio.sleep(0)
                result_list.extend(await asyncio.gather(*batch))
            return result_list

        # log time to run batch
        def log_timer(start_time, requests):
            acquire_time = time.time() - start_time
            num_samples = len(requests)
            _logger.info(
                f"Finished all {num_samples} jobs from OLI. "
                + f"Total: {acquire_time} s, "
                + f"Rate: {acquire_time/num_samples} s/sample"
            )

        loop = asyncio.new_event_loop()
        start_time = time.time()
        result_list = loop.run_until_complete(collect_results(requests, batch_size))
        log_timer(start_time, requests)
        return result_list

    async def call_async(
        self,
        flash_method=None,
        dbs_file_id=None,
        input_params=None,
        burst_job_tag=None,
        index=None,
        poll_time=0.5,
        max_request=100,
    ):
        """
        Make a call to the OLI Cloud API (async method).

        :param flash_method: string indicating flash method
        :param dbs_file_id: string name for DBS file ID
        :param input_params: dictionary for flash calculation inputs
        :param burst_job_tag: value to tag to OLI call URLs
        :param poll_time: seconds between each poll
        :param max_request: maximum number of times to try request before failure

        :return result: dictionary for JSON output result
        """

        mode, url, headers = self._get_flash_mode(dbs_file_id, flash_method, burst_job_tag)
        _logger.info(f"Submitting sample #{index+1} ...")
        req = requests.request(
            mode, url, headers=headers, data=json.dumps(input_params)
        )
        req_json = self._request_status_test(req, ["SUCCESS"])
        result_link = self._get_result_link(req_json)
        await asyncio.sleep(poll_time)
        _logger.info(f"Polling sample #{index+1} ... ")
        result = self._poll_result_link(result_link, headers, max_request, poll_time)
        _logger.info(f"Processed sample {index+1}")
        result["submitted_requests"] = {"flash_method": flash_method,
                                        "dbs_file_id": dbs_file_id,
                                        "input_params": input_params}
        return {index: result}

    def call(
        self,
        flash_method=None,
        dbs_file_id=None,
        input_params=None,
        poll_time=0.5,
        max_request=100,
    ):
        """
        Make a call to the OLI Cloud API.

        :param flash_method: string indicating flash method
        :param dbs_file_id: string name for DBS file ID
        :param input_params: dictionary for flash calculation inputs
        :param poll_time: seconds between each poll
        :param max_request: maximum number of times to try request before failure

        :return result: dictionary for JSON output result
        """

        mode, url, headers = self._get_flash_mode(dbs_file_id, flash_method)
        req = requests.request(
            mode, url, headers=headers, data=json.dumps(input_params)
        )
        req_json = self._request_status_test(req, ["SUCCESS"])
        result_link = self._get_result_link(req_json)
        time.sleep(poll_time)
        result = self._poll_result_link(result_link, headers, max_request, poll_time)
        result["submitted_requests"] = {"flash_method": flash_method,
                                        "dbs_file_id": dbs_file_id,
                                        "input_params": input_params}
        return result

    def _get_result_link(self, req_json):
        """
        Get result link from OLI Cloud request.

        :param req_json: JSON containing result of request

        :return result_link: string indicating URL to access call results
        """

        result_link = ""
        if "data" in req_json:
            if "status" in req_json["data"]:
                if req_json["data"]["status"] in ["IN QUEUE", "IN PROGRESS"]:
                    if "resultsLink" in req_json["data"]:
                        result_link = req_json["data"]["resultsLink"]
                if "resultsLink" in req_json["data"]:
                    result_link = req_json["data"]["resultsLink"]
        if not result_link:
            _logger.warning(f"Failed to get 'resultsLink'. Response: {req.json()}")
        return result_link

    def _request_status_test(self, req, target_keys):
        """
        Check result of OLI request (except async).

        :param req: response object
        :param target_keys: list containing key(s) that indicate successful request

        :return req_json: response object converted to JSON
        """

        req_json = req.json()
        func_name = sys._getframe().f_back.f_code.co_name
        _logger.debug(f"{func_name} response: {req_json}")
        if req.status_code == 200:
            if target_keys:
                if "status" in req_json:
                    if req_json["status"] in target_keys:
                        return req_json
            else:
                return req_json
        raise RuntimeError(f"Failure in {func_name}. Response: {req_json}")

    def _poll_result_link(self, result_link, headers, max_request, poll_time):
        """
        Poll result link from OLI Flash calculation request.

        :param result_link: string indicating URL to access call results
        :param headers: dictionary for OLI Cloud headers
        :param max_request: integer for number of requests before poll limit error
        :param poll_time: float for time in between poll requests

        return result: JSON containing results from successful Flash calculation
        """

        for _ in range(max_request):
            result_req = requests.get(result_link, headers=headers)
            result_req = self._request_status_test(
                result_req, ["IN QUEUE", "IN PROGRESS", "PROCESSED", "FAILED"]
            )
            _logger.info(f"Polling result link: {result_req['status']}")
            if result_req["status"] in ["PROCESSED", "FAILED"]:
                if result_req["data"]:
                    result = result_req["data"]
                    return result
            time.sleep(poll_time)
        raise RuntimeError("Poll limit exceeded.")
