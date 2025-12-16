/*-
 * ===============LICENSE_START=======================================================
 * Acumos
 * ===================================================================================
 * Copyright (C) 2017 AT&T Intellectual Property & Tech Mahindra. All rights reserved.
 * ===================================================================================
 * This Acumos software file is distributed by AT&T and Tech Mahindra
 * under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *  
 *      http://www.apache.org/licenses/LICENSE-2.0
 *  
 * This file is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ===============LICENSE_END=========================================================
 */

package org.acumos.designstudio.ce.controller;

import javax.servlet.http.HttpServletResponse;

import org.acumos.designstudio.ce.service.IAcumosCatalog;
import org.acumos.designstudio.ce.util.EELFLoggerDelegator;
import org.acumos.designstudio.ce.util.Properties;
import org.acumos.designstudio.ce.util.SanitizeUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.bind.annotation.RestController;

import io.swagger.annotations.ApiOperation;

@RestController
@RequestMapping(value = "/dsce/artifact/")
public class ArtfactDetailsController {
	private static EELFLoggerDelegator logger = EELFLoggerDelegator.getLogger(ArtfactDetailsController.class);
	@Autowired
	private IAcumosCatalog iacumosCatalog;
	@Autowired
	Properties props;

	
	/**
	 * Gets TOSCA details for specified solutionId and version
	 * @param userId
	 * 			User ID
	 * @param solutionId
	 * 			solutionId
	 * @param version
	 * 			version
	 * @param response
	 * 			response
	 * @return
	 * 			Json Response
	 */
	@ApiOperation(value = "Gets TOSCA details for specified solutionId and version")
	@RequestMapping(value = "/fetchJsonTOSCA", method = RequestMethod.GET, produces = "text/plain")
	@ResponseBody
	public String fetchJsonTOSCA(@RequestParam(value = "userId", required = true) String userId,
			@RequestParam(value = "solutionId", required = true) String solutionId,
			@RequestParam(value = "version", required = true) String version, HttpServletResponse response) {
		logger.debug(EELFLoggerDelegator.debugLogger, "fetchJsonTOSCA() : Begin");
		String result = "";
		try {
			result = iacumosCatalog.readArtifact(userId, SanitizeUtils.sanitize(solutionId), version, props.getArtifactType().trim());
			
			if (result == null || result.isEmpty()) {
				response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
				result = "Failed to fetch the TOSCA details for specified solutionId and version";				
			}
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, "Exception in fetchJsonTOSCA() ", e);
			response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
			result = e.getMessage();
		}
		logger.debug(EELFLoggerDelegator.debugLogger, "fetchJsonTOSCA() : End");
		return result;
	}

	/**
	 * @param userId
	 *            User ID
	 * @param solutionId
	 *            Solution ID
	 * @param version
	 *            Version
	 * @return Protobuf file details
	 */
	@ApiOperation(value = "Get the profobuf file details for specified solutionID and version")
	@RequestMapping(value = "/fetchProtoBufJSON", method = RequestMethod.GET, produces = "text/plain")
	@ResponseBody
	public String fetchProtoBufJSON(@RequestParam(value = "userId", required = true) String userId,
			@RequestParam(value = "solutionId", required = true) String solutionId,
			@RequestParam(value = "version", required = true) String version) {
		logger.debug(EELFLoggerDelegator.debugLogger,
				" fetchProtoBufJSON() : Begin");

		String resultTemplate = "{\"protobuf_json\" : %s,\n \"success\" : \"%s\",\n \"errorMessage\" : \"%s\"}";
		String result = "";
		try {
			result = iacumosCatalog.readArtifact(userId, SanitizeUtils.sanitize(solutionId), version, props.getProtoArtifactType().trim());

			if (result != null && !result.isEmpty()) {
				resultTemplate = String.format(resultTemplate, result, true, "");
			} else {
				resultTemplate = String.format(resultTemplate, result, false, "Unable to read protoBufFile");
			}
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, "Exception in fetchProtoBufJSON() ", e);
			resultTemplate = String.format(resultTemplate, null, false, e.getMessage());
		}
		logger.debug(EELFLoggerDelegator.debugLogger,
				"fetchProtoBufJSON() : End");
		return resultTemplate;
	}

}
