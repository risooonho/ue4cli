from .ThirdPartyLibraryDetails import PrintingFormat, ThirdPartyLibraryDetails
from .UnrealManagerException import UnrealManagerException
from .ConfigurationManager import ConfigurationManager
from .UE4BuildInterrogator import UE4BuildInterrogator
from .CachedDataManager import CachedDataManager
from .CMakeCustomFlags import CMakeCustomFlags
from .Utility import Utility
import glob, hashlib, json, os, re, shutil, sys

class UnrealManagerBase(object):
	"""
	Base class for platform-specific Unreal manager instances
	"""
	
	def clearCachedData(self):
		"""
		Clears any cached data we have stored about specific engine versions
		"""
		CachedDataManager.clearCache()
	
	def validBuildConfigurations(self):
		"""
		Returns the list of valid build configurations supported by UnrealBuildTool
		"""
		return ['Debug', 'DebugGame', 'Development', 'Shipping', 'Test']
	
	def getPlatformIdentifier(self):
		"""
		Returns the platform identifier for the current platform, as used by UnrealBuildTool
		"""
		pass
	
	def setEngineRootOverride(self, rootDir):
		"""
		Sets a user-specified directory as the root engine directory, overriding any auto-detection
		"""
		ConfigurationManager.setConfigKey('rootDirOverride', rootDir)
	
	def clearEngineRootOverride(self):
		"""
		Removes any previously-specified root engine directory override
		"""
		ConfigurationManager.setConfigKey('rootDirOverride', None)
	
	def getEngineRoot(self):
		"""
		Returns the root directory location of the latest installed version of UE4
		"""
		if not hasattr(self, '_engineRoot'):
			self._engineRoot = self._getEngineRoot()
		return self._engineRoot
	
	def getEngineVersion(self, outputFormat = 'full'):
		"""
		Returns the version number of the latest installed version of UE4
		"""
		version = self._getEngineVersionDetails()
		formats = {
			'major': version['MajorVersion'],
			'minor': version['MinorVersion'],
			'patch': version['PatchVersion'],
			'full': '{}.{}.{}'.format(version['MajorVersion'], version['MinorVersion'], version['PatchVersion']),
			'short': '{}.{}'.format(version['MajorVersion'], version['MinorVersion'])
		}
		
		# Verify that the requested output format is valid
		if outputFormat not in formats:
			raise Exception('unreconised version output format "{}"'.format(outputFormat))
		
		return formats[outputFormat]
	
	def getEngineChangelist(self):
		"""
		Returns the compatible Perforce changelist identifier for the latest installed version of UE4
		"""
		
		# Newer versions of the engine use the key "CompatibleChangelist", older ones use "Changelist"
		version = self._getEngineVersionDetails()
		if 'CompatibleChangelist' in version:
			return int(version['CompatibleChangelist'])
		else:
			return int(version['Changelist'])
	
	def getEditorBinary(self, cmdVersion=False):
		"""
		Determines the location of the UE4Editor binary
		"""
		return self.getEngineRoot() + '/Engine/Binaries/' + self.getPlatformIdentifier() + '/UE4Editor' + self._editorPathSuffix(cmdVersion)
	
	def getBuildScript(self):
		"""
		Determines the location of the script file to perform builds
		"""
		pass
	
	def getGenerateScript(self):
		"""
		Determines the location of the script file to generate IDE project files
		"""
		pass
	
	def getRunUATScript(self):
		"""
		Determines the location of the script file to run the Unreal Automation Tool
		"""
		pass
	
	def getProjectFile(self, dir):
		"""
		Detects the .uproject file for the Unreal project in the specified directory
		"""
		for project in glob.glob(dir + '/*.uproject'):
			return os.path.realpath(project)
		
		# No project detected
		raise UnrealManagerException('could not detect an Unreal project in the current directory')
	
	def getProjectName(self, dir):
		"""
		Determines the name of the Unreal project in the specified directory
		"""
		return os.path.basename(self.getProjectFile(dir)).replace('.uproject', '')
	
	def listThirdPartyLibs(self, configuration = 'Development'):
		"""
		Lists the supported Unreal-bundled third-party libraries
		"""
		interrogator = self._getUE4BuildInterrogator()
		return interrogator.list(self.getPlatformIdentifier(), configuration, self._getLibraryOverrides())
	
	def getThirdpartyLibs(self, libs, configuration = 'Development', includePlatformDefaults = True):
		"""
		Retrieves the ThirdPartyLibraryDetails instance for Unreal-bundled versions of the specified third-party libraries
		"""
		if includePlatformDefaults == True:
			libs = self._defaultThirdpartyLibs() + libs
		interrogator = self._getUE4BuildInterrogator()
		return interrogator.interrogate(self.getPlatformIdentifier(), configuration, libs, self._getLibraryOverrides())
	
	def getThirdPartyLibCompilerFlags(self, libs):
		"""
		Retrieves the compiler flags for building against the Unreal-bundled versions of the specified third-party libraries
		"""
		fmt = PrintingFormat.singleLine()
		if libs[0] == '--multiline':
			fmt = PrintingFormat.multiLine()
			libs = libs[1:]
		
		platformDefaults = True
		if libs[0] == '--nodefaults':
			platformDefaults = False
			libs = libs[1:]
		
		details = self.getThirdpartyLibs(libs, includePlatformDefaults=platformDefaults)
		return details.getCompilerFlags(self.getEngineRoot(), fmt)
	
	def getThirdPartyLibLinkerFlags(self, libs):
		"""
		Retrieves the linker flags for building against the Unreal-bundled versions of the specified third-party libraries
		"""
		fmt = PrintingFormat.singleLine()
		if libs[0] == '--multiline':
			fmt = PrintingFormat.multiLine()
			libs = libs[1:]
		
		includeLibs = True
		if (libs[0] == '--flagsonly'):
			includeLibs = False
			libs = libs[1:]
		
		platformDefaults = True
		if libs[0] == '--nodefaults':
			platformDefaults = False
			libs = libs[1:]
		
		details = self.getThirdpartyLibs(libs, includePlatformDefaults=platformDefaults)
		return details.getLinkerFlags(self.getEngineRoot(), fmt, includeLibs)
	
	def getThirdPartyLibCmakeFlags(self, libs):
		"""
		Retrieves the CMake invocation flags for building against the Unreal-bundled versions of the specified third-party libraries
		"""
		fmt = PrintingFormat.singleLine()
		if libs[0] == '--multiline':
			fmt = PrintingFormat.multiLine()
			libs = libs[1:]
		
		platformDefaults = True
		if libs[0] == '--nodefaults':
			platformDefaults = False
			libs = libs[1:]
		
		details = self.getThirdpartyLibs(libs, includePlatformDefaults=platformDefaults)
		CMakeCustomFlags.processLibraryDetails(details)
		return details.getCMakeFlags(self.getEngineRoot(), fmt)
	
	def getThirdPartyLibIncludeDirs(self, libs):
		"""
		Retrieves the list of include directories for building against the Unreal-bundled versions of the specified third-party libraries
		"""
		platformDefaults = True
		if libs[0] == '--nodefaults':
			platformDefaults = False
			libs = libs[1:]
		
		details = self.getThirdpartyLibs(libs, includePlatformDefaults=platformDefaults)
		return details.getIncludeDirectories(self.getEngineRoot(), delimiter='\n')
	
	def getThirdPartyLibFiles(self, libs):
		"""
		Retrieves the list of library files for building against the Unreal-bundled versions of the specified third-party libraries
		"""
		platformDefaults = True
		if libs[0] == '--nodefaults':
			platformDefaults = False
			libs = libs[1:]
		
		details = self.getThirdpartyLibs(libs, includePlatformDefaults=platformDefaults)
		return details.getLibraryFiles(self.getEngineRoot(), delimiter='\n')
	
	def getThirdPartyLibDefinitions(self, libs):
		"""
		Retrieves the list of preprocessor definitions for building against the Unreal-bundled versions of the specified third-party libraries
		"""
		platformDefaults = True
		if libs[0] == '--nodefaults':
			platformDefaults = False
			libs = libs[1:]
		
		details = self.getThirdpartyLibs(libs, includePlatformDefaults=platformDefaults)
		return details.getPreprocessorDefinitions(self.getEngineRoot(), delimiter='\n')
	
	def generateProjectFiles(self, dir=os.getcwd()):
		"""
		Generates IDE project files for the Unreal project in the specified directory
		"""
		genScript = self.getGenerateScript()
		projectFile = self.getProjectFile(dir)
		Utility.run([genScript, '-project=' + projectFile, '-game', '-engine'], cwd=os.path.dirname(genScript), raiseOnError=True)
	
	def cleanProject(self, dir=os.getcwd()):
		"""
		Cleans the Unreal project in the specified directory
		"""
		
		# Verify that an Unreal project exists in the specified directory
		project = self.getProjectFile(dir)
		
		# Because performing a clean will also delete the engine build itself when using
		# a source build, we simply delete the `Binaries` and `Intermediate` directories
		shutil.rmtree(os.path.join(dir, 'Binaries'), ignore_errors=True)
		shutil.rmtree(os.path.join(dir, 'Intermediate'), ignore_errors=True)
		
		# Clean any plugins
		projectPlugins = glob.glob(os.path.join(dir, 'Plugins', '*'))
		for pluginDir in projectPlugins:
			shutil.rmtree(os.path.join(pluginDir, 'Binaries'), ignore_errors=True)
			shutil.rmtree(os.path.join(pluginDir, 'Intermediate'), ignore_errors=True)
	
	def buildProject(self, dir=os.getcwd(), configuration='Development', args=[], suppressOutput=False):
		"""
		Builds the editor for the Unreal project in the specified directory, using the specified build configuration
		"""
		
		# Verify that the specified build configuration is valid
		if configuration not in self.validBuildConfigurations():
			raise UnrealManagerException('invalid build configuration "' + configuration + '"')
		
		# Perform the build
		projectFile = self.getProjectFile(dir)
		projectName = self.getProjectName(dir)
		targetName  = projectName + 'Editor'
		self._runUnrealBuildTool(targetName, self.getPlatformIdentifier(), configuration, ['-project=' + projectFile] + args, capture=suppressOutput)
	
	def runEditor(self, dir=os.getcwd(), debug=False, args=[]):
		"""
		Runs the editor for the Unreal project in the specified directory
		"""
		projectFile = self.getProjectFile(dir)
		extraFlags = ['-debug'] + args if debug == True else args
		Utility.run([self.getEditorBinary(True), projectFile, '-stdout', '-FullStdOutLogOutput'] + extraFlags, raiseOnError=True)
	
	def runUAT(self, args):
		"""
		Runs the Unreal Automation Tool with the supplied arguments
		"""
		
		# If no `-platform=PLATFORM` argument was specified, use the current platform
		platformSpecified = len([a for a in args if a.startswith('-platform=')]) > 0
		if platformSpecified == False:
			args.append('-platform=' + self.getPlatformIdentifier())
		
		# If no `-project=PROJECT` argument was specified, use the project in the current dir
		projectSpecified = len([a for a in args if a.startswith('-project=')]) > 0
		if projectSpecified == False:
			args.append('-project=' + self.getProjectFile(os.getcwd()))
		
		# Run UAT
		Utility.run([self.getRunUATScript()] + args, cwd=self.getEngineRoot(), raiseOnError=True)
	
	def packageProject(self, extraArgs):
		"""
		Packages a Shipping build of the Unreal project in the specified directory, using common packaging options
		"""
		
		# Build the Development version of the Editor, needed for cooking content
		self.buildProject()
		
		# Invoke UAT to package the Shipping build
		distDir = os.path.join(os.path.abspath(os.getcwd()), 'dist')
		self.runUAT([
			'BuildCookRun',
			'-clientconfig=Shipping',
			'-serverconfig=Shipping',
			'-noP4',
			'-cook',
			'-allmaps',
			'-build',
			'-stage',
			'-prereqs',
			'-pak',
			'-archive',
			'-archivedirectory=' + distDir
		])
	
	def runAutomationCommands(self, projectFile, commands, capture=False):
		'''
		Invokes the Automation Test commandlet for the specified project with the supplied automation test commands
		'''
		
		# IMPORTANT IMPLEMENTATION NOTE:
		# We need to format the command as a string and execute it using a shell in order to
		# ensure the "-ExecCmds" argument will be parsed correctly under Windows. This is because
		# the WinMain() function uses GetCommandLineW() to retrieve the raw command-line string,
		# rather than using an argv-style structure. The string is then passed to FParse::Value(),
		# which checks for the presence of a quote character after the equals sign to determine if
		# whitespace should be stripped or preserved. Without the quote character, the spaces in the
		# argument payload will be stripped out, corrupting our list of automation commands and
		# preventing them from executing correctly.
		
		command = '{} {}'.format(Utility.escapePathForShell(self.getEditorBinary(True)), Utility.escapePathForShell(projectFile))
		command += ' -game -buildmachine -stdout -fullstdoutlogoutput -forcelogflush -unattended -nopause -nullrhi'
		command += ' -ExecCmds="automation {};quit"'.format(';'.join(commands))
		
		if capture == True:
			return Utility.capture(command, shell=True)
		else:
			Utility.run(command, shell=True)
	
	def listAutomationTests(self, projectFile):
		'''
		Returns the list of supported automation tests for the specified project
		'''
		
		# Attempt to retrieve the list of automation tests
		tests = set()
		testRegex = re.compile('.*LogAutomationCommandLine: Display: \t(.+)')
		logOutput = self.runAutomationCommands(projectFile, ['List'], capture=True)
		for line in logOutput.stdout.split('\n'):
			matches = testRegex.search(line)
			if matches != None:
				tests.add(matches[1].strip())
		
		# Detect if the Editor terminated abnormally (i.e. not triggered by `automation quit`)
		if 'PlatformMisc::RequestExit(' not in logOutput.stdout:
			raise RuntimeError(
				'failed to retrieve the list of automation tests!' +
				' stdout was: "{}", stderr was: "{}"'.format(logOutput.stdout, logOutput.stderr)
			)
		
		return sorted(list(tests))
	
	def automationTests(self, dir=os.getcwd(), args=[]):
		'''
		Performs automation tests for the Unreal project in the specified directory
		'''
		
		# Verify that at least one argument was supplied
		if len(args) == 0:
			raise RuntimeError('at least one test name must be specified')
		
		# Build the project if it isn't already built
		Utility.printStderr('Ensuring project is built...')
		self.buildProject(dir, suppressOutput=True)
		
		# Determine which arguments we are passing to the automation test commandlet
		projectFile = self.getProjectFile(dir)
		if '--list' in args:
			Utility.printStderr('Retrieving automation test list...')
			print('\n'.join(self.listAutomationTests(projectFile)))
		else:
			
			# Sanitise the user-supplied arguments to prevent command injection
			sanitised = [arg.replace(',', '').replace(';', '') for arg in args]
			command = ['RunAll'] if '--all' in args else ['RunTests ' + '+'.join(sanitised)]
			
			# Attempt to run the automation tests
			Utility.printStderr('Running automation tests...')
			logOutput = self.runAutomationCommands(projectFile, command, capture=True)
			
			# Propagate the log output
			print(logOutput.stdout)
			print(logOutput.stderr)
			
			# Detect abnormal exit conditions (those not triggered by `automation quit`)
			if 'PlatformMisc::RequestExit(' not in logOutput.stdout:
				sys.exit(1)
			
			# If automation testing failed, propagate the failure
			errorStrings = ['Incorrect automation command syntax!', 'Automation Test Failed', 'Found 0 Automation Tests, based on']
			for errorStr in errorStrings:
				if errorStr in logOutput.stdout:
					sys.exit(1)
	
	
	# "Protected" methods
	
	def _getEngineRoot(self):
		"""
		Retrieves the user-specified engine root directory override (if set), or else performs auto-detection
		"""
		override = ConfigurationManager.getConfigKey('rootDirOverride')
		if override != None:
			Utility.printStderr('Using user-specified engine root: ' + override)
			return override
		else:
			return self._detectEngineRoot()
	
	def _detectEngineRoot(self):
		"""
		Determines the root directory location of the latest installed version of UE4
		"""
		pass
	
	def _getEngineVersionDetails(self):
		"""
		Parses the JSON version details for the latest installed version of UE4
		"""
		versionFile = self.getEngineRoot() + '/Engine/Build/Build.version'
		return json.loads(Utility.readFile(versionFile))
	
	def _getEngineVersionHash(self):
		"""
		Computes the SHA-256 hash of the JSON version details for the latest installed version of UE4
		"""
		versionDetails = self._getEngineVersionDetails()
		hash = hashlib.sha256()
		hash.update(json.dumps(versionDetails, sort_keys=True, indent=0).encode('utf-8'))
		return hash.hexdigest()
	
	def _editorPathSuffix(self, cmdVersion):
		"""
		Returns the suffix for the path to the UE4Editor binary
		"""
		pass
	
	def _runDotNetApplication(self, exeFile, args = []):
		"""
		Runs a .NET application and captures the output
		"""
		pass
	
	def _buildDotNetProject(self, projectFile):
		"""
		Builds a .NET project and captures the output
		"""
		pass
	
	def _defaultThirdpartyLibs(self):
		"""
		Returns the list of default third-party libraries to build against under the current platform
		"""
		return []
	
	def _getLibraryOverrides(self):
		"""
		Returns the dictionary of third-party library detail overrides
		"""
		return {}
	
	def _transformBuildToolPlatform(self, platform):
		"""
		Derived classes can override this method to transform platform strings when running UBT
		"""
		return platform
	
	def _runUnrealBuildTool(self, target, platform, configuration, args, capture=False):
		"""
		Invokes UnrealBuildTool with the specified parameters
		"""
		platform = self._transformBuildToolPlatform(platform)
		arguments = [self.getBuildScript(), target, platform, configuration] + args
		if capture == True:
			return Utility.capture(arguments, cwd=self.getEngineRoot(), raiseOnError=True)
		else:
			Utility.run(arguments, cwd=self.getEngineRoot(), raiseOnError=True)
	
	def _getUE4BuildInterrogator(self):
		"""
		Uses UE4BuildInterrogator to interrogate UnrealBuildTool about third-party library details
		"""
		ubtLambda = lambda target, platform, config, args: self._runUnrealBuildTool(target, platform, config, args, True)
		interrogator = UE4BuildInterrogator(self.getEngineRoot(), self._getEngineVersionHash(), ubtLambda)
		return interrogator
