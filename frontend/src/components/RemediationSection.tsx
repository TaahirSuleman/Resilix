import React from 'react'
import { RemediationPlan } from '../types/ui'
import { GitMerge, Check, ArrowRight, ExternalLink } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

interface RemediationSectionProps {
  plan: RemediationPlan
  onApproveMerge: () => void
  isApproving: boolean
}

export function RemediationSection({ plan, onApproveMerge, isApproving }: RemediationSectionProps) {
  const canApprove = plan.approvalStatus === 'pending'
  const isApproved = plan.approvalStatus === 'approved' || plan.prStatus === 'merged'

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-700 leading-relaxed">{plan.description}</p>

      <div className="border border-gray-200 rounded-md overflow-hidden bg-white">
        <div className="bg-gray-50 px-3 py-2 border-b border-gray-200 flex items-center gap-2">
          <GitMerge className="w-3 h-3 text-gray-500" />
          <span className="text-xs font-mono text-gray-600">{plan.codeDiff.filename}</span>
        </div>
        <div className="p-3 bg-white font-mono text-xs overflow-x-auto">
          {plan.codeDiff.oldLine && (
            <div className="flex gap-3 text-gray-400 line-through opacity-60">
              <span className="select-none text-gray-300 w-4 text-right">-</span>
              {plan.codeDiff.oldLine}
            </div>
          )}
          <div className="flex gap-3 text-green-700 bg-green-50/50 -mx-3 px-3 py-1">
            <span className="select-none text-green-500 w-4 text-right">+</span>
            <pre className="whitespace-pre-wrap font-inherit m-0">{plan.codeDiff.newLine}</pre>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>PR Status: {plan.prStatus.replace('_', ' ')}</span>
        {plan.prUrl ? (
          <a className="inline-flex items-center gap-1 text-blue-600" href={plan.prUrl} target="_blank" rel="noreferrer">
            View PR <ExternalLink className="w-3 h-3" />
          </a>
        ) : null}
      </div>

      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>Jira: {plan.jiraKey ?? 'Not created'}</span>
        {plan.jiraUrl ? (
          <a className="inline-flex items-center gap-1 text-blue-600" href={plan.jiraUrl} target="_blank" rel="noreferrer">
            Open Jira <ExternalLink className="w-3 h-3" />
          </a>
        ) : null}
      </div>

      <div className="pt-2 flex justify-end">
        <motion.button
          onClick={onApproveMerge}
          disabled={!canApprove || isApproving}
          whileTap={!isApproved && canApprove ? { scale: 0.97 } : {}}
          className={`
            relative overflow-hidden flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors
            ${
              isApproved
                ? 'bg-green-600 text-white cursor-default'
                : canApprove
                  ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm hover:shadow'
                  : 'bg-gray-200 text-gray-500 cursor-not-allowed'
            }
          `}
        >
          <AnimatePresence mode="wait">
            {isApproved ? (
              <motion.div
                key="approved"
                initial={{
                  y: 10,
                  opacity: 0,
                }}
                animate={{
                  y: 0,
                  opacity: 1,
                }}
                className="flex items-center gap-2"
              >
                <Check className="w-4 h-4" />
                <span>Approved & Merged</span>
              </motion.div>
            ) : (
              <motion.div
                key="approve"
                exit={{
                  y: -10,
                  opacity: 0,
                }}
                className="flex items-center gap-2"
              >
                <GitMerge className="w-4 h-4" />
                <span>{isApproving ? 'Approving...' : 'Approve Merge'}</span>
                <ArrowRight className="w-4 h-4" />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.button>
      </div>
    </div>
  )
}
