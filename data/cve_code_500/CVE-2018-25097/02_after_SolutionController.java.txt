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

import java.util.ArrayList;
import java.util.List;

import javax.servlet.http.HttpServletRequest;
import javax.validation.Valid;

import org.acumos.designstudio.ce.exceptionhandler.AcumosException;
import org.acumos.designstudio.ce.service.ICompositeSolutionService;
import org.acumos.designstudio.ce.service.ISolutionService;
import org.acumos.designstudio.ce.util.ConfigurationProperties;
import org.acumos.designstudio.ce.util.DSUtil;
import org.acumos.designstudio.ce.util.EELFLoggerDelegator;
import org.acumos.designstudio.ce.util.Properties;
import org.acumos.designstudio.ce.util.SanitizeUtils;
import org.acumos.designstudio.ce.vo.DSCompositeSolution;
import org.acumos.designstudio.ce.vo.SuccessErrorMessage;
import org.acumos.designstudio.ce.vo.cdump.DataConnector;
import org.acumos.designstudio.ce.vo.cdump.Nodes;
import org.acumos.designstudio.ce.vo.cdump.Property;
import org.acumos.designstudio.ce.vo.cdump.collator.CollatorMap;
import org.acumos.designstudio.ce.vo.cdump.databroker.DataBrokerMap;
import org.acumos.designstudio.ce.vo.cdump.datamapper.DataMap;
import org.acumos.designstudio.ce.vo.cdump.datamapper.FieldMap;
import org.acumos.designstudio.ce.vo.cdump.datamapper.MapInputs;
import org.acumos.designstudio.ce.vo.cdump.datamapper.MapOutput;
import org.acumos.designstudio.ce.vo.cdump.splitter.SplitterMap;
import org.json.JSONArray;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.bind.annotation.RestController;

import com.google.gson.Gson;
import com.google.gson.JsonParser;

import io.swagger.annotations.ApiOperation;

/**
 * 
 *
 *
 */
@RestController
@RequestMapping(value = "/dsce/solution/")
public class SolutionController {
	private final EELFLoggerDelegator logger = EELFLoggerDelegator.getLogger(SolutionController.class);

	@Autowired
	Properties props;

	@Autowired
	ConfigurationProperties confprops;

	@Autowired
	@Qualifier("solutionServiceImpl")
	ISolutionService solutionService;

	@Autowired
	@Qualifier("compositeServiceImpl")
	ICompositeSolutionService compositeServiceImpl;

	/**
	 * 
	 * @param userId
	 *            User ID
	 * @return Solutions
	 * @throws AcumosException
	 *             On failure
	 */
	@ApiOperation(value = "Get Solutions for specified userId")
	@RequestMapping(value = "/getSolutions", method = RequestMethod.GET)
	public String getSolutions(@RequestParam(value = "userId", defaultValue = "1") String userId)
			throws AcumosException {
		String result = null;
		String resultTemplate = "{\"items\" : %s}";
		String error = "{errorCode : \"%s\", errorDescription : \"%s\"}";
		try {
			logger.debug(EELFLoggerDelegator.debugLogger, " getSolutions() Begin ");
			result = solutionService.getSolutions(userId);
			result = String.format(resultTemplate, result);
		} catch (AcumosException e) {
			logger.error(EELFLoggerDelegator.errorLogger, " Exception in getSolutions() ", e);
			result = String.format(error, e.getErrorCode(), e.getErrorDesc());
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, "Exception in getSolutions()", e);
			result = String.format(error, props.getSolutionErrorCode(), props.getSolutionErrorDesc());
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " getSolutions() End ");
		return result;
	}

	@ApiOperation(value = "Save the Composite Solution")
	@RequestMapping(value = "/saveCompositeSolution", method = RequestMethod.POST)
	@ResponseBody
	public Object saveCompositeSolution(HttpServletRequest request,
			@RequestParam(value = "userId", required = true) String userId,
			@RequestParam(value = "solutionName", required = true) String solutionName,
			@RequestParam(value = "version", required = true) String version,
			@RequestParam(value = "solutionId", required = false) String solutionId,
			@RequestParam(value = "description", required = true) String description,
			@RequestParam(value = "cid", required = false) String cid,
			@RequestParam(value = "ignoreLesserVersionConflictFlag", required = true, defaultValue = "false") boolean ignoreLesserVersionConflictFlag)
			throws AcumosException {

		String result = "";
		String error = "{\"errorCode\" : \"%s\", \"errorDescription\" : \"%s\"}";
		logger.debug(EELFLoggerDelegator.debugLogger, " saveCompositeSolution() Begin ");

		DSCompositeSolution dscs = new DSCompositeSolution();

		try {
			dscs.setAuthor(userId);
			dscs.setSolutionName(solutionName);
			dscs.setSolutionId(SanitizeUtils.sanitize(solutionId));
			dscs.setVersion(version);
			dscs.setOnBoarder(userId);
			dscs.setDescription(description);
			dscs.setProvider(props.getProvider());
			dscs.setToolKit(props.getToolKit());
			dscs.setVisibilityLevel(props.getVisibilityLevel());
			dscs.setcId(cid);
			dscs.setIgnoreLesserVersionConflictFlag(ignoreLesserVersionConflictFlag);

			// 1. JSON Validation
			if (DSUtil.isValidJSON(dscs.toJsonString())) {
				logger.debug(EELFLoggerDelegator.debugLogger, " SuccessFully validated inputJson ");
				// 2. Mandatory Value validation
				String isValidmsg = checkMandatoryFieldsforSave(dscs);

				if (null != isValidmsg) {
					result = String.format(error, "603", isValidmsg);
				} else {
					logger.debug(EELFLoggerDelegator.debugLogger,
							" SuccessFully validated mandatory fields ");
					result = compositeServiceImpl.saveCompositeSolution(dscs);
				}
			} else {
				result = String.format(error, "200", "Incorrectly formatted input – Invalid JSON");
			}

		} catch (AcumosException e) {
			logger.error(EELFLoggerDelegator.errorLogger, " Exception in getSolutions() ", e);
			result = String.format(error, e.getErrorCode(), e.getErrorDesc());
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, " Exception in getSolutions() ", e);
			result = String.format(error, props.getCompositionSolutionErrorCode(),
					props.getCompositionSolutionErrorDesc());
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " saveCompositeSolution() End ");
		return result;
	}

	public String checkMandatoryFieldsforSave(DSCompositeSolution dscs) {
		List<String> errorList = new ArrayList<>();

		if (null == dscs.getAuthor().trim()) {
			errorList.add("UserID is missing");
		}
		if (null == dscs.getSolutionName().trim()) {
			errorList.add("Solution Name is missing");
		}
		if (null == dscs.getVersion()) {
			errorList.add("Version is missing");
		}
		if (null == dscs.getSolutionId() && null == dscs.getcId()) {
			errorList.add("Either cid or Solution Id is required");
		}
		if (!errorList.isEmpty()) {
			return errorList.toString();
		} else {
			return null;
		}

	}

	@ApiOperation(value = "create new Composition Solution")
	@RequestMapping(value = "/createNewCompositeSolution", method = RequestMethod.POST)
	public String createNewCompositeSolution(@RequestParam(value = "userId", required = true) String userId) {
		String results = "";
		logger.debug(EELFLoggerDelegator.debugLogger, " createNewCompositeSolution()  : Begin");
		try {
			results = solutionService.createNewCompositeSolution(userId);
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, "Exception in  createNewCompositeSolution() ",
					e);
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " createNewCompositeSolution()  : End");
		return results;
	}

	@ApiOperation(value = "add Node Operation")
	@RequestMapping(value = "/addNode", method = RequestMethod.POST)
	public String addNode(@RequestParam(value = "userId", required = true) String userId,
			@RequestParam(value = "solutionId", required = false) String solutionId,
			@RequestParam(value = "version", required = false) String version,
			@RequestParam(value = "cid", required = false) String cid, @RequestBody @Valid Nodes node) {
		String results = "";
		logger.debug(EELFLoggerDelegator.debugLogger, " addNode()  : Begin");
		try {

			boolean validNode = validateNode(node);
			if (validNode) {
				if ((solutionId != null && version != null) || (null != cid)) {
					results = solutionService.addNode(userId, SanitizeUtils.sanitize(solutionId), version, cid, node);
				} else {
					results = "{\"error\": \"Either Cid or SolutionId and Version need to Pass\"}";
				}
			} else {
				results = "{\"error\": \"JSON schema not valid, Please check the input JSON\"}";
			}
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, "Exception in  addNode() ", e);
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " addNode()  : End");
		return results;

	}

	/**
	 * 
	 * @param node
	 * @return
	 */
	private boolean validateNode(Nodes node) {
		boolean result = false;
		boolean nameFlag = false;
		boolean nodeIdFlag = false;
		boolean nodeSolutionIdFlag = false;
		boolean nodeVersionFlag = false;
		boolean requirementsFlag = false;
		boolean capabilitiesFlag = false;
		boolean ndataFlag = false;
		boolean typeFlag = false;
		if (null != node.getName() && node.getName().trim().length() > 0) {
			nameFlag = true;
		}
		if (null != node.getNodeId() && node.getNodeId().trim().length() > 0) {
			nodeIdFlag = true;
		}
		if (null != node.getNodeSolutionId() && node.getNodeSolutionId().trim().length() > 0) {
			nodeSolutionIdFlag = true;
		}
		if (null != node.getNodeVersion() && node.getNodeVersion().trim().length() > 0) {
			nodeVersionFlag = true;
		}
		if (null != node.getRequirements()) {
			requirementsFlag = true;
		}
		if (null != node.getCapabilities()) {
			capabilitiesFlag = true;
		}
		if (null != node.getNdata()) {
			ndataFlag = true;
		}
		if (null != node.getType()) {
			typeFlag = true;
		}
		if (nameFlag && nodeIdFlag && nodeSolutionIdFlag && nodeVersionFlag && requirementsFlag && capabilitiesFlag
				&& ndataFlag && typeFlag) {
			result = true;
		}
		return result;
	}

	@ApiOperation(value = "Gets existing composite solution details for specified solutionId and version")
	@RequestMapping(value = "/readCompositeSolutionGraph", method = RequestMethod.GET, produces = "text/plain")
	@ResponseBody
	public String readCompositeSolutionGraph(@RequestParam(value = "userId", required = true) String userId,
			@RequestParam(value = "solutionId", required = true) String solutionId,
			@RequestParam(value = "version", required = true) String version) {
		logger.debug(EELFLoggerDelegator.debugLogger, " fetchJsonTOSCA()  : Begin");
		String result;
		try {
			result = solutionService.readCompositeSolutionGraph(userId, SanitizeUtils.sanitize(solutionId), version);
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, "Failed to read the ComposietSolution", e);
			result = "";
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " fetchJsonTOSCA()  : End");
		return result;
	}

	private String validateAddLinkInputs(String sourceNodeName, String linkId, String targetNodeName,
			String targetNodeCapabilityName, String sourceNodeId) {
		List<String> errList = new ArrayList<>();

		if (sourceNodeName == null) {
			errList.add("Source Node name missing" + " ");
		}
		if (linkId == null) {
			errList.add("Link missing" + " ");
		}
		if (targetNodeName == null) {
			errList.add("target Node name missing" + " ");
		}
		if (targetNodeCapabilityName == null) {
			errList.add("targetNodeCapabilityName mising" + " ");

			if (sourceNodeId == null) {
				errList.add("sourceNodeId mising" + " ");
			}
		}
		return errList.toString();
	}

	@ApiOperation(value = "Modify Node Operation")
	@RequestMapping(value = "/modifyNode", method = RequestMethod.POST)
	@ResponseBody
	public String modifyNode(@RequestParam(value = "userid", required = true) String userId,
			@RequestParam(value = "solutionid", required = false) String solutionId,
			@RequestParam(value = "version", required = false) String version,
			@RequestParam(value = "cid", required = false) String cid,
			@RequestParam(value = "nodeid", required = true) String nodeId,
			@RequestParam(value = "nodename", required = false) String nodeName,
			@RequestParam(value = "ndata", required = false) String ndata,
			@RequestBody(required = false) DataConnector dataConnector) {
		
		String result = null;
		FieldMap fieldMap = null;
		DataBrokerMap databrokerMap = null;
		CollatorMap collatorMap = null;
		SplitterMap  splitterMap = null;
		logger.debug(EELFLoggerDelegator.debugLogger, "------- modifyNode() ------- : Begin");
		try {
			if(null != dataConnector){
				if(null != dataConnector.getFieldMap()){
					fieldMap = dataConnector.getFieldMap();
				}
				if(null != dataConnector.getDatabrokerMap()){
					databrokerMap = dataConnector.getDatabrokerMap();
				}
				if(null != dataConnector.getCollatorMap()){
					collatorMap = dataConnector.getCollatorMap();
				}
				if(null != dataConnector.getSplitterMap()){
					splitterMap = dataConnector.getSplitterMap();
				}
			}
			result = solutionService.modifyNode(userId, SanitizeUtils.sanitize(solutionId), version, cid, nodeId, nodeName, ndata, fieldMap, databrokerMap, collatorMap, splitterMap);
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, "-------Exception in  modifyNode() -------", e);
		}
		logger.debug(EELFLoggerDelegator.debugLogger, "------- modifyNode() ------- : End");
		return result;
	}

	@ApiOperation(value = "Modify Link Operation")
	@RequestMapping(value = "/modifyLink", method = RequestMethod.POST)
	@ResponseBody
	public String modifyLink(@RequestParam(value = "userid", required = true) String userId,
			@RequestParam(value = "cid", required = false) String cid,
			@RequestParam(value = "solutionid", required = false) String solutionId,
			@RequestParam(value = "version", required = false) String version,
			@RequestParam(value = "linkid", required = true) String linkId,
			@RequestParam(value = "linkname", required = true) String linkName) {
		String result = null;
		logger.debug(EELFLoggerDelegator.debugLogger, " modifyLink()  : Begin");
		try {
			result = solutionService.modifyLink(userId, cid, SanitizeUtils.sanitize(solutionId), version, linkId, linkName);
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, "Exception in  modifyLink() ", e);
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " modifyLink()  : End");
		return result;
	}

	@ApiOperation(value = "Delete the CompositeSolution")
	@RequestMapping(value = "/deleteCompositeSolution", method = RequestMethod.POST)
	@ResponseBody
	public String deleteCompositeSolution(@RequestParam(value = "userid", required = true) String userId,
			@RequestParam(value = "solutionid", required = true) String solutionId,
			@RequestParam(value = "version", required = true) String version) {
		String resultTemplate = "{\"success\":\"%s\",\"errorMessage\":\"%s\"}";
		String result = "";
		logger.debug(EELFLoggerDelegator.debugLogger, " deleteCompositeSolution()  : Begin");

		try {

			boolean deleted = compositeServiceImpl.deleteCompositeSolution(userId, SanitizeUtils.sanitize(solutionId), version);
			if (!deleted) {
				result = String.format(resultTemplate, "false", "Requested Solution Not Found");
			} else {
				result = String.format(resultTemplate, "true", "");
			}
		} catch (Exception e) {
			logger.debug(EELFLoggerDelegator.debugLogger, "Exception in  deleteCompositeSolution() ", e);
			result = String.format(resultTemplate, "false", "Exception : Requested Solution Not Found");
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " deleteCompositeSolution()  : End");
		return result;
	}

	@ApiOperation(value = "delete Node Operation")
	@RequestMapping(value = "/deleteNode", method = RequestMethod.POST)
	public String deleteNode(@RequestParam(value = "userId", required = true) String userId,
			@RequestParam(value = "solutionId", required = false) String solutionId,
			@RequestParam(value = "version", required = false) String version,
			@RequestParam(value = "cid", required = false) String cid,
			@RequestParam(value = "nodeId", required = true) String nodeId) {
		logger.debug(EELFLoggerDelegator.debugLogger, " deleteNode() in SolutionController Begin ");
		String result = "";
		String resultTemplate = "{\"success\":\"%s\", \"errorMessage\":\"%s\"}";
		if (null == userId && null == nodeId) {
			result = String.format(resultTemplate, false, "Mandatory feild(s) missing");
		} else {
			try {
				boolean deletedNode = solutionService.deleteNode(userId, SanitizeUtils.sanitize(solutionId), version, cid, nodeId);
				if (deletedNode) {
					result = String.format(resultTemplate, true, "");
				} else {
					result = String.format(resultTemplate, false, "Invalid Node Id – not found");
				}
			} catch (Exception e) {
				logger.error(EELFLoggerDelegator.errorLogger,
						" Exception in deleteNode() in SolutionController ", e);
			}
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " deleteNode() in SolutionController Ends ");
		return result;
	}

	@ApiOperation(value = "Close Composite Solution Operation")
	@RequestMapping(value = "/closeCompositeSolution ", method = RequestMethod.POST)
	@ResponseBody
	public String closeCompositeSolution(@RequestParam(value = "userId", required = true) String userId,
			@RequestParam(value = "solutionId", required = false) String solutionId,
			@RequestParam(value = "solutionVersion", required = false) String solutionVersion,
			@RequestParam(value = "cid", required = false) String cid) {
		logger.debug(EELFLoggerDelegator.debugLogger, " closeCompositeSolution(): Begin ");
		String result = "";
		try {
			result = compositeServiceImpl.closeCompositeSolution(userId, SanitizeUtils.sanitize(solutionId), solutionVersion, cid);
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, " Exception in closeCompositeSolution() ", e);
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " closeCompositeSolution(): End ");
		return result;
	}

	@ApiOperation(value = "Clear Composite Solution Operation")
	@RequestMapping(value = "/clearCompositeSolution", method = RequestMethod.POST)
	@ResponseBody
	public String clearCompositeSolution(@RequestParam(value = "userId", required = true) String userId,
			@RequestParam(value = "solutionId", required = false) String solutionId,
			@RequestParam(value = "solutionVersion", required = false) String solutionVersion,
			@RequestParam(value = "cid", required = false) String cid) {
		logger.debug(EELFLoggerDelegator.debugLogger, " clearCompositeSolution(): Begin ");
		String result = "";
		try {
			result = compositeServiceImpl.clearCompositeSolution(userId, SanitizeUtils.sanitize(solutionId), solutionVersion, cid);
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, " Exception in clearCompositeSolution() ", e);
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " clearCompositeSolution(): End ");
		return result;

	}

	@ApiOperation(value = "Fetch the list of active public Composite Solution for the specified User Id")
	@RequestMapping(value = "/getCompositeSolutions", method = RequestMethod.GET, produces = "text/plain")
	@ResponseBody
	public String getCompositeSolutions(@RequestParam(value = "userId", required = true) String userId,
			@RequestParam(value = "visibilityLevel", required = true) String visibilityLevel) {
		logger.debug(EELFLoggerDelegator.debugLogger, " getCompositeSolutions()  : Begin");
		String result = "";
		String resultTemplate = "{\"items\" : %s}";
		String error = "{errorCode : \"%s\", errorDescription : \"%s\"}";
		try {
			visibilityLevel = visibilityLevel.toUpperCase();
			result = compositeServiceImpl.getCompositeSolutions(userId, visibilityLevel);
			result = String.format(resultTemplate, result);
		} catch (AcumosException e) {
			logger.error(EELFLoggerDelegator.errorLogger, " Exception in getCompositeSolutions() ", e);
			result = String.format(error, e.getErrorCode(), e.getErrorDesc());
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, " Exception in getCompositeSolutions()", e);
			result = String.format(error, "401", "Failed to fetch the list of active Public Composite Solutions");
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " getCompositeSolutions()  : End");
		return result;
	}

	@ApiOperation(value = "Fetch the all the maching models for any specified model")
	@RequestMapping(value = "/getMatchingModels", method = RequestMethod.GET, produces = "text/plain")
	@ResponseBody
	public String getMatchingModels(@RequestParam(value = "userId", required = false) String userId,
			@RequestParam(value = "solutionId", required = false) String solutionId,
			@RequestParam(value = "solutionVersion", required = false) String solutionVersion,
			@RequestParam(value = "cid", required = false) String cid,
			@RequestParam(value = "portType", required = true) String portType,
			@RequestParam(value = "protobufJsonString", required = true) JSONArray protobufJsonString) {
		logger.debug(EELFLoggerDelegator.debugLogger, " getMatchingModels()  : Begin");
		String result = "";
		String resultTemplate = "{\"success\" : %s,\"matchingModels\" : %s}";
		String error = "{\"error\" : %s";
		try {
			result = solutionService.getMatchingModels(userId, portType, protobufJsonString);
			if (!result.equals("false")) {
				result = String.format(resultTemplate, "true", result);
			} else {
				result = String.format(resultTemplate, "false", "No matching models found");
			}
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, " Exception in getMatchingModels() ", e);
			result = String.format(error, e.getMessage());
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " getMatchingModels()  : End");
		return result;
	}

	@ApiOperation(value = "Validate Composite Solution")
	@RequestMapping(value = "/validateCompositeSolution", method = RequestMethod.POST, produces = "text/plain")
	@ResponseBody
	public String validateCompositeSolution(@RequestParam(value = "userId", required = true) String userId,
			@RequestParam(value = "solutionName", required = true) String solutionName,
			@RequestParam(value = "solutionId", required = true) String solutionId,
			@RequestParam(value = "version", required = true) String version) {
		logger.debug(EELFLoggerDelegator.debugLogger, "validateCompositeSolution() : Begin ");
		String result = "";
		try {
			result = compositeServiceImpl.validateCompositeSolution(userId, solutionName, SanitizeUtils.sanitize(solutionId), version);
			result = String.format(result);
		} catch (Exception e) {
			result = "{\"success\" : \"false\", \"errorDescription\" : \"Failed to Validate Composite Solution\"}";
			result = String.format(result);
			logger.debug(EELFLoggerDelegator.errorLogger, " Exception in validateCompositeSolution() ", e);
			e.printStackTrace();
		}
		logger.debug(EELFLoggerDelegator.debugLogger, "validateCompositeSolution() : End ");
		return result;
	}

	@ApiOperation(value = "add link Operation")
	@RequestMapping(value = "/addLink", method = RequestMethod.POST)
	public String addLink(@RequestParam(value = "userId", required = true) String userId,
			@RequestParam(value = "solutionId", required = false) String solutionId,
			@RequestParam(value = "version", required = false) String version,
			@RequestParam(value = "cid", required = false) String cid,
			@RequestParam(value = "linkName", required = false) String linkName,
			@RequestParam(value = "linkId", required = true) String linkId,
			@RequestParam(value = "sourceNodeName", required = true) String sourceNodeName,
			@RequestParam(value = "sourceNodeId", required = true) String sourceNodeId,
			@RequestParam(value = "targetNodeName", required = true) String targetNodeName,
			@RequestParam(value = "targetNodeId", required = true) String targetNodeId,
			@RequestParam(value = "sourceNodeRequirement", required = true) String sourceNodeRequirement,
			@RequestParam(value = "targetNodeCapabilityName", required = true) String targetNodeCapabilityName,
			@RequestBody(required = false) @Valid org.acumos.designstudio.ce.vo.cdump.Property property) { // Change in API signature

		logger.debug(EELFLoggerDelegator.debugLogger, " addLink()  : Begin");

		String result = null;
		boolean linkAdded = false;
		String resultTemplate = "{\"success\" : \"%s\", \"errorDescription\" : \"%s\"}";

		try {
			if (linkId != null && sourceNodeName != null && targetNodeName != null && targetNodeId != null
					&& targetNodeCapabilityName != null) {

				if (validateProperty(property)) {
					linkAdded = solutionService.addLink(userId, SanitizeUtils.sanitize(solutionId), version, linkName, linkId, sourceNodeName,
							sourceNodeId, targetNodeName, targetNodeId, sourceNodeRequirement, targetNodeCapabilityName,
							cid, property);

					if (linkAdded) {
						result = String.format(resultTemplate, true, "");
					} else {
						result = String.format(resultTemplate, false, "Link not added");
					}

				} else {
					result = String.format(resultTemplate, false, "Invalid input: properties");
				}
			} else {
				result = validateAddLinkInputs(sourceNodeName, linkId, targetNodeName, targetNodeCapabilityName,
						sourceNodeId);
			}
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, " Exception in addLink() ", e);
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " addLink()  : End");
		return result;
	}

	/**
	 * 
	 * @param property
	 * @return
	 */
	private boolean validateProperty(Property property) {

		logger.debug(EELFLoggerDelegator.debugLogger, " validateProperty()  : Begin");

		Gson gson = new Gson();
		boolean isValid = false;
		DataMap dMap = new DataMap();
		dMap = property.getData_map();
		boolean map_inputsFlag = false;
		boolean map_outputsFlag = false;
		JsonParser parser = new JsonParser();

		try {
			// if link if b/w 2 models
			if (null == property || (null != property && null == property.getData_map())) {
				map_inputsFlag = true;
				map_outputsFlag = true;
			} else {
				// validate JSON structure if link is b/w model & Data mapper
				parser.parse(gson.toJson(property));
				// validate map_inputs
				if (dMap.getMap_outputs().length == 0) {
					MapInputs[] map_inputs = dMap.getMap_inputs();
					if (map_inputs != null && map_inputs.length != 0) {
						for (int i = 0; i < map_inputs.length; i++) {
							if (map_inputs[i].getMessage_name() != null && map_inputs[i].getInput_fields() != null
									&& map_inputs[i].getInput_fields().length != 0) {
								map_inputsFlag = true;
								map_outputsFlag = true;
							}
						}
					}
				}
				// validate map_outputs
				if (dMap.getMap_inputs().length == 0) {
					MapOutput[] map_outputs = dMap.getMap_outputs();
					if (map_outputs != null && map_outputs.length != 0) {
						for (int i = 0; i < map_outputs.length; i++) {
							if (map_outputs[i].getMessage_name() != null && map_outputs[i].getOutput_fields() != null
									&& map_outputs[i].getOutput_fields().length != 0) {
								map_outputsFlag = true;
								map_inputsFlag = true;
							}
						}
					}
				}
			}
			if (map_outputsFlag == true && map_inputsFlag == true) {
				isValid = true;
			}
		} catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, " Exception in validateProperty() ", e);
			isValid = false;
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " validateProperty()  : End");
		return isValid;
	}

	@ApiOperation(value = "delete link Operation")
	@RequestMapping(value = "/deleteLink", method = RequestMethod.POST)
	public String deleteLink(@RequestParam(value = "userId", required = true) String userId,
			@RequestParam(value = "cid", required = false) String cid,
			@RequestParam(value = "solutionId", required = false) String solutionId,
			@RequestParam(value = "version", required = false) String version,
			@RequestParam(value = "linkId", required = true) String linkId) {

		logger.debug(EELFLoggerDelegator.debugLogger, " deleteLink() in SolutionController begins -");
		String result = "";
		String resultTemplate = "{\"success\":\"%s\", \"errorMessage\":\"%s\"}";
		if (null == userId && null == linkId) {
			result = String.format(resultTemplate, false, "Mandatory feild(s) missing");
		} else {
			try {
				boolean deletedLink = solutionService.deleteLink(userId, SanitizeUtils.sanitize(solutionId), version, cid, linkId);
				if (deletedLink) {
					result = String.format(resultTemplate, true, "");
				} else {
					result = String.format(resultTemplate, false, "Invalid Link Id – not found");
				}
			} catch (Exception e) {
				logger.error(EELFLoggerDelegator.errorLogger,
						" Exception in deleteLink() in SolutionController ", e);
			}
		}
		logger.debug(EELFLoggerDelegator.debugLogger, " deleteLink() in SolutionController Ends ");
		return result;
	}
	@ApiOperation(value = "set the ProbeIndicator")
	@RequestMapping(value = "/setProbeIndicator", method = RequestMethod.POST)
	public @ResponseBody SuccessErrorMessage setProbeIndicator(HttpServletRequest request,
			@RequestParam(value = "userId", required = true) String userId,
			@RequestParam(value = "solutionId", required = false) String solutionId,
			@RequestParam(value = "version", required = true) String version,
			@RequestParam(value = "cid", required = false) String cid,
			@RequestParam(value = "probeIndicator", required = true) String probeIndicator
			)
			throws AcumosException {
        SuccessErrorMessage successErrorMessage = null;
		logger.debug(EELFLoggerDelegator.debugLogger, "setProbeIndicator() in SolutionController Begin");
        try {
        	successErrorMessage = compositeServiceImpl.setProbeIndicator(userId, SanitizeUtils.sanitize(solutionId), version, cid,probeIndicator);
		}catch (Exception e) {
			logger.error(EELFLoggerDelegator.errorLogger, "Exception in setProbeIndicator() in SolutionController", e);
		}
		logger.debug(EELFLoggerDelegator.debugLogger, "setProbeIndicator() in SolutionController End");
		return successErrorMessage;
	}
}
