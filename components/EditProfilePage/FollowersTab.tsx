import { functions } from "components/firebase"
import { httpsCallable } from "firebase/functions"
import type {
  GetFollowersRequest,
  GetFollowersResponse
} from "functions/src/subscriptions/getFollowers"
import { useTranslation } from "next-i18next"
import { Dispatch, SetStateAction, useEffect, useState } from "react"
import { useAuth } from "../auth"
import { UsersCard } from "./FollowableItemsCard"

export const getFollowers = httpsCallable<
  GetFollowersRequest,
  GetFollowersResponse
>(functions, "getFollowers")

export const FollowersTab = ({
  className,
  setFollowerCount
}: {
  className?: string
  setFollowerCount: Dispatch<SetStateAction<number | null>>
}) => {
  const uid = useAuth().user?.uid
  const [followerIds, setFollowerIds] = useState<string[]>([])
  const { t } = useTranslation("editProfile")

  useEffect(() => {
    const fetchFollowers = async (uid: string) => {
      try {
        const response = await getFollowers({ uid })
        setFollowerIds(response.data)
        setFollowerCount(response.data.length)
      } catch (err) {
        console.error("Error fetching followerIds", err)
        return
      }
    }
    if (uid) fetchFollowers(uid)
  }, [uid])

  return (
    <UsersCard
      className={className}
      title={t("follow.your_followers")}
      subtitle={t("follow.private_follower_info_disclaimer")}
      items={followerIds.map(profileId => ({ profileId }))}
    />
  )
}
