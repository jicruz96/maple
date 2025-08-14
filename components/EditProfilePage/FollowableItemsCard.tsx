import { usePublicProfile } from "components/db"
import { Internal } from "components/links"
import {
  FollowButtonProps,
  FollowUserButton,
  UserItem
} from "components/shared/FollowButton"
import React from "react"
import { Col, Row, Spinner, Stack } from "../bootstrap"
import { TitledSectionCard } from "../shared"
import { OrgIconSmall } from "./StyledEditProfileComponents"

export function FollowableItemsCard<Item>({
  className,
  title,
  subtitle,
  items,
  ItemCard
}: {
  className?: string
  title: string
  subtitle?: string
  items: Item[]
  ItemCard: React.FC<Item>
}) {
  return (
    <TitledSectionCard className={className}>
      <div className={`mx-4 mt-3 d-flex flex-column gap-3`}>
        <Stack>
          <h2>{title}</h2>
          {subtitle ? <p className="mt-0 text-muted">{subtitle}</p> : null}
          <div className="mt-3">
            {items.map((item, i) => (
              <ItemCard key={i} {...item} />
            ))}
          </div>
        </Stack>
      </div>
    </TitledSectionCard>
  )
}

export function FollowableItemsCardWith<Item>(
  config: Pick<
    React.ComponentProps<typeof FollowableItemsCard<Item>>,
    "ItemCard"
  >
): React.FC<
  Omit<React.ComponentProps<typeof FollowableItemsCard<Item>>, "ItemCard">
> {
  return props => <FollowableItemsCard {...props} {...config} />
}

export function FollowableItemCard({
  loading,
  followButton,
  content
}: {
  loading: boolean
  followButton: JSX.Element
  content: JSX.Element
}) {
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

export const UsersCard = FollowableItemsCardWith<UserItem>({
  ItemCard: props => {
    const { profileId } = props
    const { result: profile, loading } = usePublicProfile(profileId)
    const { profileImage, fullName } = profile || {}
    return (
      <FollowableItemCard
        loading={loading}
        content={
          <>
            <OrgIconSmall
              className="mr-4 mt-0 mb-0 ms-0"
              profileImage={profileImage}
            />
            <Internal href={`/profile?id=${profileId}`}>{fullName}</Internal>
          </>
        }
        followButton={
          <FollowUserButton
            fullName={fullName}
            confirmUnfollow={true}
            {...props}
          />
        }
      />
    )
  }
})
