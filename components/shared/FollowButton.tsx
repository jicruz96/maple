import { StyledImage } from "components/ProfilePage/StyledProfileComponents"
import { useTranslation } from "next-i18next"
import { useEffect, useContext, useState } from "react"
import { Button } from "react-bootstrap"
import { TopicQuery, followTopic, unfollowTopic } from "./FollowingQueries"
import { FollowContext } from "./FollowContext"
import { Modal } from "../bootstrap"
import { FillButton, OutlineButton } from "components/buttons"
import { formatBillId } from "components/formatting"
import { useAuth } from "components/auth"

export type BillItem = {
  court: number
  billId: string
}
export type UserItem = {
  profileId: string
  fullName?: string
}
export interface BaseFollowButtonProps {
  onFollow?: () => Promise<void>
  onUnfollow?: () => Promise<void>
  confirmFollow?: boolean
  confirmUnfollow?: boolean
  hide?: boolean
}
const ConfirmFollowToggleModal = ({
  show,
  displayName,
  onConfirm,
  onDeny,
  action
}: {
  show: boolean
  displayName: string
  onConfirm: () => Promise<void>
  onDeny: () => Promise<void>
  action: "follow" | "unfollow"
}) => {
  const { t } = useTranslation("common")
  return (
    <Modal
      show={show}
      onHide={onDeny}
      aria-labelledby={`${action}-modal`}
      centered
    >
      <Modal.Header closeButton>
        <Modal.Title id={`${action}-modal`}>
          {t(`button.follow.${action}`)}
        </Modal.Title>
      </Modal.Header>
      <Modal.Body className={`ms-auto me-auto p-3 `}>
        <div className={`d-flex flex-wrap text-center px-5`}>
          {t("button.follow.confirmation_modal.message", {
            action,
            name: displayName
          })}
        </div>
        <div className={`d-flex gap-3 px-2 col-6 mt-4 mr-4`}>
          <OutlineButton
            className={`col-3 ms-auto`}
            onClick={onDeny}
            label={t("button.follow.confirmation_modal.no")}
          />
          <FillButton
            className={`col-3 me-auto`}
            onClick={onConfirm}
            label={t("button.follow.confirmation_modal.yes")}
          />
        </div>
      </Modal.Body>
    </Modal>
  )
}

export const BaseFollowButton = ({
  topicName,
  displayName,
  onFollow,
  onUnfollow,
  confirmFollow,
  confirmUnfollow,
  hide
}: BaseFollowButtonProps & {
  topicName: string
  displayName: string
}) => {
  const { t } = useTranslation("common")
  const uid = useAuth().user?.uid
  const { followStatus, setFollowStatus } = useContext(FollowContext)

  useEffect(() => {
    uid
      ? TopicQuery(uid, topicName).then(result => {
          setFollowStatus(prevOrgFollowGroup => {
            return { ...prevOrgFollowGroup, [topicName]: Boolean(result) }
          })
        })
      : null
  }, [uid, topicName, setFollowStatus])

  const isFollowing = followStatus[topicName]
  const [showModal, setShowModal] = useState(false)
  const wantsConfirm = isFollowing ? confirmUnfollow : confirmFollow

  const toggleFollow = async () => {
    if (isFollowing) {
      if (onUnfollow) await onUnfollow()
      setFollowStatus(prev => ({ ...prev, [topicName]: false }))
    } else {
      if (onFollow) await onFollow()
      setFollowStatus(prev => ({ ...prev, [topicName]: true }))
    }
  }

  return (
    <>
      {!hide && (
        <div className="follow-button">
          <Button
            type="button"
            onClick={async () =>
              wantsConfirm ? setShowModal(true) : await toggleFollow()
            }
            className="btn btn-lg py-1"
          >
            {t(`button.follow.${isFollowing ? "following" : "follow"}`)}
            {isFollowing ? <StyledImage src="/check-white.svg" alt="" /> : null}
          </Button>
        </div>
      )}
      <ConfirmFollowToggleModal
        show={showModal}
        onConfirm={async () => {
          await toggleFollow()
          setShowModal(false)
        }}
        onDeny={async () => setShowModal(false)}
        displayName={displayName}
        action={isFollowing ? "unfollow" : "follow"}
      />
    </>
  )
}

export function FollowUserButton({
  profileId,
  fullName,
  onUnfollow,
  onFollow,
  ...rest
}: UserItem & BaseFollowButtonProps) {
  const uid = useAuth().user?.uid
  const topicName = `testimony-${profileId}`
  const { t } = useTranslation("common")
  return (
    <BaseFollowButton
      topicName={topicName}
      onFollow={async () => {
        followTopic({
          type: "testimony",
          uid,
          topicName,
          data: { userLookup: { profileId } }
        })
        if (onFollow) await onFollow()
      }}
      onUnfollow={async () => {
        unfollowTopic(uid, topicName)
        if (onUnfollow) await onUnfollow()
      }}
      displayName={fullName || t("modal.this_user")}
      {...rest}
    />
  )
}

export function FollowBillButton({
  billId,
  court,
  onFollow,
  onUnfollow,
  ...rest
}: BillItem & BaseFollowButtonProps) {
  const topicName = `bill-${court}-${billId}`
  const uid = useAuth().user?.uid
  const { t } = useTranslation("common")
  return (
    <BaseFollowButton
      topicName={topicName}
      onFollow={async () => {
        followTopic({
          type: "bill",
          uid,
          topicName,
          data: { billLookup: { billId, court } }
        })
        if (onFollow) await onFollow()
      }}
      onUnfollow={async () => {
        unfollowTopic(uid, topicName)
        if (onUnfollow) await onUnfollow()
      }}
      displayName={t("bill.bill", { billId: formatBillId(billId) })}
      {...rest}
    />
  )
}
