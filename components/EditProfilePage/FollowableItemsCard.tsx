import { usePublicProfile } from "components/db"
import { Internal } from "components/links"
import {
  BaseFollowButtonProps,
  FollowUserButton
} from "components/shared/FollowButton"
import React from "react"
import { Col, Row, Spinner, Stack } from "../bootstrap"
import { TitledSectionCard } from "../shared"
import { OrgIconSmall } from "./StyledEditProfileComponents"

export type BillItem = {
  court: number
  billId: string
}
export type UserItem = {
  profileId: string
  fullName?: string
}
export type FollowableItemsCard<Item> = React.FC<{
  className?: string
  title: string
  subtitle?: string
  items: (Item & BaseFollowButtonProps)[]
}>
type FollowableItemProps = {
  loading: boolean
  followButton: JSX.Element
  content: JSX.Element
}

export function createFollowableItemsCard<Item>(
  toFollowableItemProps: (
    item: Item & BaseFollowButtonProps
  ) => FollowableItemProps
): FollowableItemsCard<Item> {
  return ({ items, className, title, subtitle }) => (
    <TitledSectionCard className={className}>
      <div className={`mx-4 mt-3 d-flex flex-column gap-3`}>
        <Stack>
          <h2>{title}</h2>
          {subtitle ? <p className="mt-0 text-muted">{subtitle}</p> : null}
          <div className="mt-3">
            {items.map(toFollowableItemProps).map(FollowableItem)}
          </div>
        </Stack>
      </div>
    </TitledSectionCard>
  )
}

function FollowableItem({
  loading,
  followButton,
  content
}: FollowableItemProps) {
  if (loading) {
    return <Spinner animation="border" className="mx-auto" />
  }
  return (
    <div className={`fs-3 lh-lg`}>
      <Row className="align-items-center justify-content-between g-0 w-100">
        <Col className="d-flex align-items-center flex-grow-1 p-0 text-start">
          {content}
        </Col>
        <Col
          xs="auto"
          className="d-flex justify-content-end ms-auto text-end p-0"
        >
          {followButton}
        </Col>
      </Row>
      <hr className={`mt-3`} />
    </div>
  )
}

export const UsersCard: FollowableItemsCard<UserItem> =
  createFollowableItemsCard<UserItem>(item => {
    const { profileId } = item
    const { result: profile, loading } = usePublicProfile(profileId)
    const { profileImage, fullName } = profile || {}
    return {
      loading,
      content: (
        <>
          <OrgIconSmall
            className="mr-4 mt-0 mb-0 ms-0"
            profileImage={profileImage}
          />
          <Internal href={`/profile?id=${profileId}`}>{fullName}</Internal>
        </>
      ),
      followButton: (
        <FollowUserButton
          fullName={fullName}
          confirmUnfollow={true}
          {...item}
        />
      )
    }
  })
