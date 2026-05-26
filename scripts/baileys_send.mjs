#!/usr/bin/env node
import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  useMultiFileAuthState,
} from '@whiskeysockets/baileys'
import P from 'pino'
import qrcode from 'qrcode-terminal'
import { mkdir } from 'node:fs/promises'
import { homedir } from 'node:os'
import path from 'node:path'

const DEFAULT_SESSION_DIR = path.join(homedir(), '.config', 'knowledge-os', 'baileys-auth')

function parseArgs(argv) {
  const args = {
    sessionDir: process.env.BAILEYS_SESSION_DIR || DEFAULT_SESSION_DIR,
    timeoutMs: Number(process.env.BAILEYS_TIMEOUT_MS || 60000),
    maxConnectAttempts: Number(process.env.BAILEYS_CONNECT_ATTEMPTS || 3),
    loginOnly: false,
  }
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    switch (arg) {
      case '--to':
        args.to = argv[++index]
        break
      case '--message':
        args.message = argv[++index]
        break
      case '--session-dir':
        args.sessionDir = argv[++index]
        break
      case '--timeout-ms':
        args.timeoutMs = Number(argv[++index])
        break
      case '--connect-attempts':
        args.maxConnectAttempts = Number(argv[++index])
        break
      case '--login-only':
        args.loginOnly = true
        break
      case '-h':
      case '--help':
        args.help = true
        break
      default:
        throw new Error(`Unknown argument: ${arg}`)
    }
  }
  return args
}

function usage() {
  console.log(`Usage: node scripts/baileys_send.mjs [options]

Options:
  --to PHONE             E.164 phone number, e.g. +919179611575
  --message TEXT         WhatsApp message body
  --session-dir PATH     Auth session directory, defaults to ~/.config/knowledge-os/baileys-auth
  --timeout-ms N         Connect/send timeout, defaults to 60000
  --connect-attempts N   Socket reconnect attempts for restart-required handshakes, defaults to 3
  --login-only           Connect and save a linked session without sending
  -h, --help             Show this help

First run prints a WhatsApp QR code. Open WhatsApp > Linked devices > Link a device.
`)
}

function jidForPhone(phone) {
  const digits = String(phone || '').replace(/\D/g, '')
  if (!digits) {
    throw new Error('--to must contain a phone number')
  }
  return `${digits}@s.whatsapp.net`
}

function statusCodeFromDisconnect(lastDisconnect) {
  return lastDisconnect?.error?.output?.statusCode
}

function isRestartRequired(lastDisconnect) {
  const statusCode = statusCodeFromDisconnect(lastDisconnect)
  return statusCode === DisconnectReason.restartRequired || statusCode === 515
}

async function withTimeout(promise, timeoutMs, label) {
  let timeout
  const timer = new Promise((_, reject) => {
    timeout = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms`)), timeoutMs)
  })
  try {
    return await Promise.race([promise, timer])
  } finally {
    clearTimeout(timeout)
  }
}

async function connectOnce(sessionDir, timeoutMs) {
  await mkdir(sessionDir, { recursive: true })
  const logger = P({ level: process.env.BAILEYS_LOG_LEVEL || 'silent' })
  const { state, saveCreds } = await useMultiFileAuthState(sessionDir)
  const { version } = await fetchLatestBaileysVersion()
  const sock = makeWASocket({
    auth: state,
    browser: ['Knowledge OS', 'Chrome', '1.0.0'],
    logger,
    markOnlineOnConnect: false,
    printQRInTerminal: false,
    version,
  })

  sock.ev.on('creds.update', saveCreds)

  await withTimeout(new Promise((resolve, reject) => {
    sock.ev.on('connection.update', (update) => {
      const { connection, lastDisconnect, qr } = update
      if (qr) {
        console.error('Scan this QR code with WhatsApp > Linked devices > Link a device:')
        qrcode.generate(qr, { small: true }, (code) => console.error(code))
      }
      if (connection === 'open') {
        resolve()
      }
      if (connection === 'close') {
        const statusCode = statusCodeFromDisconnect(lastDisconnect)
        if (statusCode === DisconnectReason.loggedOut) {
          reject(new Error(`WhatsApp session logged out. Remove ${sessionDir} and link again.`))
        } else if (isRestartRequired(lastDisconnect)) {
          reject(Object.assign(new Error('WhatsApp stream restart required'), { restartRequired: true }))
        } else {
          reject(new Error(lastDisconnect?.error?.message || 'WhatsApp connection closed before opening'))
        }
      }
    })
  }), timeoutMs, 'WhatsApp connection')

  return sock
}

async function connect(sessionDir, timeoutMs, maxAttempts) {
  let lastError
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return await connectOnce(sessionDir, timeoutMs)
    } catch (error) {
      lastError = error
      if (!error.restartRequired || attempt === maxAttempts) {
        break
      }
      console.error(`WhatsApp stream requested restart; reconnecting (${attempt + 1}/${maxAttempts})...`)
    }
  }
  throw lastError
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  if (args.help) {
    usage()
    return
  }
  if (!args.loginOnly && (!args.to || !args.message)) {
    throw new Error('--to and --message are required unless --login-only is used')
  }
  if (!Number.isFinite(args.timeoutMs) || args.timeoutMs <= 0) {
    throw new Error('--timeout-ms must be a positive number')
  }
  if (!Number.isFinite(args.maxConnectAttempts) || args.maxConnectAttempts <= 0) {
    throw new Error('--connect-attempts must be a positive number')
  }

  const sock = await connect(args.sessionDir, args.timeoutMs, args.maxConnectAttempts)
  try {
    if (args.loginOnly) {
      console.log(JSON.stringify({ ok: true, loginOnly: true, sessionDir: args.sessionDir }))
      return
    }

    const jid = jidForPhone(args.to)
    const result = await withTimeout(
      sock.sendMessage(jid, { text: args.message }),
      args.timeoutMs,
      'WhatsApp send',
    )
    console.log(JSON.stringify({
      ok: true,
      to: args.to,
      jid,
      messageId: result?.key?.id || null,
      sessionDir: args.sessionDir,
    }))
  } finally {
    sock.end?.()
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(`baileys_send: ${error.message}`)
    process.exit(1)
  })
