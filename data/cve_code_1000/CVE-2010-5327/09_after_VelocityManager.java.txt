/**
 * Copyright (c) 2000-2012 Liferay, Inc. All rights reserved.
 *
 * This library is free software; you can redistribute it and/or modify it under
 * the terms of the GNU Lesser General Public License as published by the Free
 * Software Foundation; either version 2.1 of the License, or (at your option)
 * any later version.
 *
 * This library is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
 * details.
 */

package com.liferay.portal.velocity;

import com.liferay.portal.kernel.template.Template;
import com.liferay.portal.kernel.template.TemplateContextType;
import com.liferay.portal.kernel.template.TemplateException;
import com.liferay.portal.kernel.template.TemplateManager;
import com.liferay.portal.kernel.util.PropsKeys;
import com.liferay.portal.kernel.util.StringUtil;
import com.liferay.portal.security.lang.PortalSecurityManagerThreadLocal;
import com.liferay.portal.security.pacl.PACLClassLoaderUtil;
import com.liferay.portal.security.pacl.PACLPolicy;
import com.liferay.portal.security.pacl.PACLPolicyManager;
import com.liferay.portal.template.RestrictedTemplate;
import com.liferay.portal.template.TemplateContextHelper;
import com.liferay.portal.util.PropsUtil;
import com.liferay.portal.util.PropsValues;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.apache.commons.collections.ExtendedProperties;
import org.apache.velocity.VelocityContext;
import org.apache.velocity.app.VelocityEngine;
import org.apache.velocity.runtime.RuntimeConstants;
import org.apache.velocity.runtime.resource.loader.StringResourceLoader;
import org.apache.velocity.runtime.resource.util.StringResourceRepository;
import org.apache.velocity.util.introspection.SecureUberspector;

/**
 * @author Raymond Augé
 */
public class VelocityManager implements TemplateManager {

	public void clearCache() {
		StringResourceRepository stringResourceRepository =
			StringResourceLoader.getRepository();

		if (stringResourceRepository != null) {
			StringResourceRepositoryImpl stringResourceRepositoryImpl =
				(StringResourceRepositoryImpl)stringResourceRepository;

			stringResourceRepositoryImpl.removeAll();
		}

		LiferayResourceCacheUtil.removeAll();
	}

	public void clearCache(String templateId) {
		StringResourceRepository stringResourceRepository =
			StringResourceLoader.getRepository();

		if (stringResourceRepository != null) {
			stringResourceRepository.removeStringResource(templateId);
		}

		LiferayResourceCacheUtil.remove(templateId);
	}

	public void destroy() {
		StringResourceLoader.clearRepositories();

		_classLoaderVelocityContexts.clear();

		_classLoaderVelocityContexts = null;
		_restrictedVelocityContext = null;
		_standardVelocityContext = null;
		_velocityEngine = null;
		_templateContextHelper = null;
	}

	public void destroy(ClassLoader classLoader) {
		_classLoaderVelocityContexts.remove(classLoader);
	}

	public Template getTemplate(
		String templateId, String templateContent, String errorTemplateId,
		String errorTemplateContent, TemplateContextType templateContextType) {

		if (templateContextType.equals(TemplateContextType.CLASS_LOADER)) {

			// This template will have all of its utilities initialized within
			// the class loader of the current thread

			ClassLoader contextClassLoader =
				PACLClassLoaderUtil.getContextClassLoader();

			PACLPolicy threadLocalPACLPolicy =
				PortalSecurityManagerThreadLocal.getPACLPolicy();

			PACLPolicy contextClassLoaderPACLPolicy =
				PACLPolicyManager.getPACLPolicy(contextClassLoader);

			try {
				PortalSecurityManagerThreadLocal.setPACLPolicy(
					contextClassLoaderPACLPolicy);

				VelocityContext velocityContext =
					_classLoaderVelocityContexts.get(contextClassLoader);

				if (velocityContext == null) {
					velocityContext = new VelocityContext();

					Map<String, Object> helperUtilities =
						_templateContextHelper.getHelperUtilities();

					for (Map.Entry<String, Object> entry :
							helperUtilities.entrySet()) {

						velocityContext.put(entry.getKey(), entry.getValue());
					}

					_classLoaderVelocityContexts.put(
						contextClassLoader, velocityContext);
				}

				return new PACLVelocityTemplate(
					templateId, templateContent, errorTemplateId,
					errorTemplateContent, velocityContext, _velocityEngine,
					_templateContextHelper, contextClassLoaderPACLPolicy);
			}
			finally {
				PortalSecurityManagerThreadLocal.setPACLPolicy(
					threadLocalPACLPolicy);
			}
		}
		else if (templateContextType.equals(TemplateContextType.EMPTY)) {
			return new VelocityTemplate(
				templateId, templateContent, errorTemplateId,
				errorTemplateContent, null, _velocityEngine,
				_templateContextHelper);
		}
		else if (templateContextType.equals(TemplateContextType.RESTRICTED)) {
			return new RestrictedTemplate(
				new VelocityTemplate(
					templateId, templateContent, errorTemplateId,
					errorTemplateContent, _restrictedVelocityContext,
					_velocityEngine, _templateContextHelper),
				_templateContextHelper.getRestrictedVariables());
		}
		else if (templateContextType.equals(TemplateContextType.STANDARD)) {
			return new VelocityTemplate(
				templateId, templateContent, errorTemplateId,
				errorTemplateContent, _standardVelocityContext, _velocityEngine,
				_templateContextHelper);
		}

		return null;
	}

	public Template getTemplate(
		String templateId, String templateContent, String errorTemplateId,
		TemplateContextType templateContextType) {

		return getTemplate(
			templateId, templateContent, errorTemplateId, null,
			templateContextType);
	}

	public Template getTemplate(
		String templateId, String templateContent,
		TemplateContextType templateContextType) {

		return getTemplate(
			templateId, templateContent, null, null, templateContextType);
	}

	public Template getTemplate(
		String templateId, TemplateContextType templateContextType) {

		return getTemplate(templateId, null, null, null, templateContextType);
	}

	public String getTemplateManagerName() {
		return VELOCITY;
	}

	public boolean hasTemplate(String templateId) {
		return _velocityEngine.resourceExists(templateId);
	}

	public void init() throws TemplateException {
		if (_velocityEngine != null) {
			return;
		}

		_velocityEngine = new VelocityEngine();

		LiferayResourceLoader.setVelocityResourceListeners(
			PropsValues.VELOCITY_ENGINE_RESOURCE_LISTENERS);

		ExtendedProperties extendedProperties = new FastExtendedProperties();

		extendedProperties.setProperty(
			VelocityEngine.EVENTHANDLER_METHODEXCEPTION,
			LiferayMethodExceptionEventHandler.class.getName());

		extendedProperties.setProperty(
			RuntimeConstants.INTROSPECTOR_RESTRICT_CLASSES,
			StringUtil.merge(PropsValues.VELOCITY_ENGINE_RESTRICTED_CLASSES));

		extendedProperties.setProperty(
			RuntimeConstants.INTROSPECTOR_RESTRICT_PACKAGES,
			StringUtil.merge(PropsValues.VELOCITY_ENGINE_RESTRICTED_PACKAGES));

		extendedProperties.setProperty(
			VelocityEngine.RESOURCE_LOADER, "string,servlet");

		extendedProperties.setProperty(
			"servlet." + VelocityEngine.RESOURCE_LOADER + ".cache",
			String.valueOf(
				PropsValues.VELOCITY_ENGINE_RESOURCE_MANAGER_CACHE_ENABLED));

		extendedProperties.setProperty(
			"servlet." + VelocityEngine.RESOURCE_LOADER + ".class",
			LiferayResourceLoader.class.getName());

		extendedProperties.setProperty(
			"string." + VelocityEngine.RESOURCE_LOADER + ".cache",
			String.valueOf(
				PropsValues.VELOCITY_ENGINE_RESOURCE_MANAGER_CACHE_ENABLED));

		extendedProperties.setProperty(
			"string." + VelocityEngine.RESOURCE_LOADER + ".class",
			StringResourceLoader.class.getName());

		extendedProperties.setProperty(
			"string." + VelocityEngine.RESOURCE_LOADER + ".repository.class",
			StringResourceRepositoryImpl.class.getName());

		extendedProperties.setProperty(
			VelocityEngine.RESOURCE_MANAGER_CLASS,
			PropsUtil.get(PropsKeys.VELOCITY_ENGINE_RESOURCE_MANAGER));

		extendedProperties.setProperty(
			VelocityEngine.RESOURCE_MANAGER_CACHE_CLASS,
			PropsUtil.get(PropsKeys.VELOCITY_ENGINE_RESOURCE_MANAGER_CACHE));

		extendedProperties.setProperty(
			VelocityEngine.RUNTIME_LOG_LOGSYSTEM_CLASS,
			PropsUtil.get(PropsKeys.VELOCITY_ENGINE_LOGGER));

		extendedProperties.setProperty(
			VelocityEngine.RUNTIME_LOG_LOGSYSTEM + ".log4j.category",
			PropsUtil.get(PropsKeys.VELOCITY_ENGINE_LOGGER_CATEGORY));

		extendedProperties.setProperty(
			RuntimeConstants.UBERSPECT_CLASSNAME,
			SecureUberspector.class.getName());

		extendedProperties.setProperty(
			VelocityEngine.VM_LIBRARY,
			PropsUtil.get(PropsKeys.VELOCITY_ENGINE_VELOCIMACRO_LIBRARY));

		extendedProperties.setProperty(
			VelocityEngine.VM_LIBRARY_AUTORELOAD,
			String.valueOf(
				!PropsValues.VELOCITY_ENGINE_RESOURCE_MANAGER_CACHE_ENABLED));

		extendedProperties.setProperty(
			VelocityEngine.VM_PERM_ALLOW_INLINE_REPLACE_GLOBAL,
			String.valueOf(
				!PropsValues.VELOCITY_ENGINE_RESOURCE_MANAGER_CACHE_ENABLED));

		_velocityEngine.setExtendedProperties(extendedProperties);

		try {
			_velocityEngine.init();
		}
		catch (Exception e) {
			throw new TemplateException(e);
		}

		_restrictedVelocityContext = new VelocityContext();

		Map<String, Object> helperUtilities =
			_templateContextHelper.getRestrictedHelperUtilities();

		for (Map.Entry<String, Object> entry : helperUtilities.entrySet()) {
			_restrictedVelocityContext.put(entry.getKey(), entry.getValue());
		}

		_standardVelocityContext = new VelocityContext();

		helperUtilities = _templateContextHelper.getHelperUtilities();

		for (Map.Entry<String, Object> entry : helperUtilities.entrySet()) {
			_standardVelocityContext.put(entry.getKey(), entry.getValue());
		}
	}

	public void setTemplateContextHelper(
		TemplateContextHelper templateContextHelper) {

		_templateContextHelper = templateContextHelper;
	}

	private Map<ClassLoader, VelocityContext> _classLoaderVelocityContexts =
		new ConcurrentHashMap<ClassLoader, VelocityContext>();
	private VelocityContext _restrictedVelocityContext;
	private VelocityContext _standardVelocityContext;
	private TemplateContextHelper _templateContextHelper;
	private VelocityEngine _velocityEngine;

}