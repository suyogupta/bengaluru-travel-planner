# State Transitions

The following tables show the state transitions for both purchase and payment requests.

## Purchase Request State Transition Matrix

| Previous Action               | Disputed                      | DisputedWithdrawn  | FundsLocked                 | FundsOrDatumInvalid | RefundRequested               | RefundWithdrawn    | ResultSubmitted             | Withdrawn          |
| ----------------------------- | ----------------------------- | ------------------ | --------------------------- | ------------------- | ----------------------------- | ------------------ | --------------------------- | ------------------ |
| Ignore                        | Ignore                        | Ignore             | Ignore                      | Ignore              | Ignore                        | Ignore             | Ignore                      | Ignore             |
| FundsLockingInitiated         | WaitingForManual\*            | WaitingForManual\* | WaitingForExternal          | WaitingForManual\*  | WaitingForManual\*            | WaitingForManual\* | WaitingForManual\*          | WaitingForManual\* |
| FundsLockingRequested         | WaitingForManual\*            | WaitingForManual\* | WaitingForManual\*          | WaitingForManual\*  | WaitingForManual\*            | WaitingForManual\* | WaitingForManual\*          | WaitingForManual\* |
| None                          | WaitingForManual\*            | WaitingForManual\* | WaitingForManual\*          | WaitingForManual\*  | WaitingForManual\*            | WaitingForManual\* | WaitingForManual\*          | WaitingForManual\* |
| SetRefundRequestedInitiated   | WaitingForExternal            | WaitingForManual\* | SetRefundRequestedRequested | WaitingForManual\*  | WaitingForExternal            | WaitingForManual\* | SetRefundRequestedRequested | WaitingForManual\* |
| SetRefundRequestedRequested   | SetRefundRequestedRequested   | WaitingForManual\* | SetRefundRequestedRequested | WaitingForManual\*  | SetRefundRequestedRequested   | WaitingForManual\* | SetRefundRequestedRequested | WaitingForManual\* |
| UnSetRefundRequestedInitiated | UnSetRefundRequestedRequested | WaitingForManual\* | WaitingForExternal          | WaitingForManual\*  | UnSetRefundRequestedRequested | WaitingForManual\* | WaitingForExternal          | WaitingForManual\* |
| UnSetRefundRequestedRequested | UnSetRefundRequestedRequested | WaitingForManual\* | WaitingForManual\*          | WaitingForManual\*  | UnSetRefundRequestedRequested | WaitingForManual\* | WaitingForManual\*          | WaitingForManual\* |
| WaitingForExternalAction      | WaitingForExternal            | None               | WaitingForExternal          | WaitingForManual\*  | WaitingForExternal            | None               | WaitingForExternal          | None               |
| WaitingForManualAction        | WaitingForManual\*            | WaitingForManual\* | WaitingForManual\*          | WaitingForManual\*  | WaitingForManual\*            | WaitingForManual\* | WaitingForManual\*          | WaitingForManual\* |
| WithdrawRefundInitiated       | WithdrawRefundRequested       | WaitingForManual\* | WithdrawRefundRequested     | WaitingForManual\*  | WithdrawRefundRequested       | None               | WaitingForManual\*          | WaitingForManual\* |
| WithdrawRefundRequested       | WithdrawRefundRequested       | WaitingForManual\* | WithdrawRefundRequested     | WaitingForManual\*  | WithdrawRefundRequested       | None               | WaitingForManual\*          | WaitingForManual\* |

## Payment Request State Transition Matrix

| Previous Action          | Disputed                 | DisputedWithdrawn  | FundsLocked           | FundsOrDatumInvalid | RefundRequested       | RefundWithdrawn    | ResultSubmitted          | Withdrawn          |
| ------------------------ | ------------------------ | ------------------ | --------------------- | ------------------- | --------------------- | ------------------ | ------------------------ | ------------------ |
| Ignore                   | Ignore                   | Ignore             | Ignore                | Ignore              | Ignore                | Ignore             | Ignore                   | Ignore             |
| AuthorizeRefundInitiated | AuthorizeRefundRequested | WaitingForManual\* | WaitingForManual\*    | WaitingForManual\*  | WaitingForExternal    | WaitingForManual\* | AuthorizeRefundRequested | WaitingForManual\* |
| AuthorizeRefundRequested | AuthorizeRefundRequested | WaitingForManual\* | WaitingForManual\*    | WaitingForManual\*  | WaitingForManual\*    | WaitingForManual\* | AuthorizeRefundRequested | WaitingForManual\* |
| None                     | WaitingForManual\*       | WaitingForManual\* | WaitingForManual\*    | WaitingForManual\*  | WaitingForManual\*    | WaitingForManual\* | WaitingForManual\*       | WaitingForManual\* |
| SubmitResultInitiated    | WaitingForExternal       | WaitingForManual\* | SubmitResultRequested | WaitingForManual\*  | SubmitResultRequested | WaitingForManual\* | WaitingForExternal       | WaitingForManual\* |
| SubmitResultRequested    | SubmitResultRequested    | WaitingForManual\* | SubmitResultRequested | WaitingForManual\*  | SubmitResultRequested | WaitingForManual\* | SubmitResultRequested    | WaitingForManual\* |
| WaitingForExternalAction | WaitingForExternal       | None               | WaitingForExternal    | WaitingForManual\*  | WaitingForExternal    | None               | WaitingForExternal       | None               |
| WaitingForManualAction   | WaitingForManual\*       | WaitingForManual\* | WaitingForManual\*    | WaitingForManual\*  | WaitingForManual\*    | WaitingForManual\* | WaitingForManual\*       | WaitingForManual\* |
| WithdrawInitiated        | WithdrawRequested        | WaitingForManual\* | WaitingForManual\*    | WaitingForManual\*  | WaitingForManual\*    | WaitingForManual\* | WaitingForManual\*       | None               |
| WithdrawRequested        | WithdrawRequested        | WaitingForManual\* | WaitingForManual\*    | WaitingForManual\*  | WaitingForManual\*    | WaitingForManual\* | WaitingForManual\*       | WaitingForManual\* |

## Legend

| Symbol/Term        | Meaning                  |
| ------------------ | ------------------------ |
| \*                 | Indicates error state    |
| WaitingForExternal | WaitingForExternalAction |
| WaitingForManual   | WaitingForManualAction   |
