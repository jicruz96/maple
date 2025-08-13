import { functions } from "components/firebase"
import { httpsCallable } from "firebase/functions"
import type {
  GetFollowersRequest,
  GetFollowersResponse
} from "functions/src/subscriptions/getFollowers"
import { useTranslation } from "next-i18next"
import { Dispatch, SetStateAction, useEffect, useState } from "react"
import { useAuth } from "../auth"
import { FollowableItemsCard, UsersCard } from "./FollowableItemsCard"

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
  const [followers, setFollowers] = useState<string[]>([])
  const { t } = useTranslation("editProfile")

  useEffect(() => {
    const fetchFollowers = async (uid: string) => {
      try {
        const response = await getFollowers({ uid })
        setFollowers(response.data)
        setFollowerCount(response.data.length)
      } catch (err) {
        console.error("Error fetching followers", err)
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
      items={followers.map(profileId => ({ profileId }))}
    />
  )
}
